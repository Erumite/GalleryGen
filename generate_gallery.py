#!/usr/bin/env python3
"""
generate_gallery.py — Python port of generate_gallery.bash

Generates a self-contained HTML photo gallery with folder navigation,
lightbox viewer, face-detection bounding boxes, and EXIF metadata.

Requires: exiftool  https://exiftool.org
Build:    pip install pyinstaller && pyinstaller --onefile generate_gallery.py
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _pause_if_gui_launch() -> None:
    """On Windows, if launched by double-clicking (no console), pause so the
    user can read any error message before the window closes."""
    if sys.platform == 'win32' and getattr(sys, 'frozen', False) and len(sys.argv) == 1:
        input("\nPress Enter to close...")


# ---------------------------------------------------------------------------
# HTML template — split at the two injection points
# ---------------------------------------------------------------------------

_HTML_PART1 = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Gallery</title>
    <style>
        :root { --bg: #1e1e1e; --surface: #2d2d2d; --text: #ffffff; --accent: #4CAF50; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 20px; }

        #breadcrumbs { font-size: 20px; margin-bottom: 20px; padding: 10px; background: var(--surface); border-radius: 8px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        #breadcrumb-path { flex: 1; min-width: 0; }
        #search-container { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
        #search-toggle { cursor: pointer; color: #aaa; padding: 4px 6px; border-radius: 6px; line-height: 0; transition: 0.2s; }
        #search-toggle:hover, #search-toggle.active { color: var(--accent); }
        #search-bar { display: none; align-items: center; gap: 6px; }
        #search-bar.open { display: flex; }
        #search-input { background: #3a3a3a; border: 1px solid #555; color: white; border-radius: 6px; padding: 5px 10px; font-size: 14px; width: 200px; outline: none; transition: border-color 0.2s, width 0.3s; }
        #search-input:focus { border-color: var(--accent); width: 260px; }
        #search-btn { background: var(--accent); color: white; border: none; border-radius: 6px; padding: 5px 12px; cursor: pointer; font-size: 14px; font-weight: bold; transition: 0.2s; }
        #search-btn:hover { background: #45a049; }
        #search-close-btn { background: none; color: #888; border: none; cursor: pointer; font-size: 20px; padding: 0 4px; line-height: 1; transition: color 0.2s; }
        #search-close-btn:hover { color: white; }
        .breadcrumb-link { color: var(--accent); cursor: pointer; text-decoration: none; }
        .breadcrumb-link:hover { text-decoration: underline; }
        .section-title { margin-top: 30px; border-bottom: 1px solid #444; padding-bottom: 5px; }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; margin-top: 15px; }

        .folder { background: var(--surface); padding: 30px 20px; border-radius: 12px; text-align: center; cursor: pointer; transition: 0.2s; }
        .folder:hover { transform: translateY(-5px); background: #3d3d3d; }
        .folder svg { width: 60px; height: 60px; fill: #F8D775; margin-bottom: 10px; }
        .folder-name { word-break: break-all; font-weight: bold; }

        .image-card { aspect-ratio: 1; overflow: hidden; border-radius: 12px; cursor: pointer; background: var(--surface); }
        .image-card img { width: 100%; height: 100%; object-fit: cover; transition: 0.3s; }
        .image-card img:hover { transform: scale(1.08); }

        #lightbox { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.95); z-index: 1000; flex-direction: column; justify-content: center; align-items: center; }
        .lightbox-content-wrapper { display: flex; flex-direction: column; align-items: center; max-height: 95vh; max-width: 90vw; }
        #img-wrapper { position: relative; display: inline-block; line-height: 0; }
        #lightbox-img { max-width: 90vw; max-height: 75vh; width: auto; height: auto; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }

        #faces-container { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
        #img-wrapper:hover .face-box { opacity: 1; }

        .face-box { position: absolute; border: 2px solid rgba(255, 255, 255, 0.6); border-radius: 2px; opacity: 0; transition: 0.2s; pointer-events: auto; box-sizing: border-box; }
        .face-box:hover { border-color: #4CAF50; box-shadow: 0 0 8px rgba(76, 175, 80, 0.8); z-index: 10; }
        .face-name { position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.4); color: white; padding: 8px 4px; border-radius: 4px; font-size: 13px; white-space: nowrap; pointer-events: none; opacity: 0; transition: 0.2s; margin-bottom: 4px; font-weight: bold; }
        .face-box:hover .face-name { opacity: 1; }

        #metadata-panel { width: 100%; margin-top: 15px; color: #ccc; font-size: 15px; line-height: 1.5; text-align: center; }
        #metadata-panel .meta-row { margin-bottom: 6px; }
        .meta-label { color: #888; font-weight: bold; margin-right: 5px; }

        .nav-btn { position: absolute; top: 40%; transform: translateY(-50%); font-size: 50px; color: white; cursor: pointer; user-select: none; padding: 20px; background: rgba(0,0,0,0.5); border-radius: 50%; width: 60px; height: 60px; display: flex; justify-content: center; align-items: center; transition: 0.2s; }
        .nav-btn:hover { background: rgba(255,255,255,0.2); }
        #prev { left: 30px; }
        #next { right: 30px; }
        #close { position: absolute; top: 20px; right: 30px; font-size: 50px; color: white; cursor: pointer; }
        .disabled { opacity: 0.2; pointer-events: none; }

        /* ── Slideshow ──────────────────────────────────────────────── */
        #slideshow-toggle { cursor: pointer; color: #aaa; padding: 4px 6px; border-radius: 6px; line-height: 0; transition: 0.2s; }
        #slideshow-toggle:hover { color: var(--accent); }
        #slideshow-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #000; z-index: 2000; justify-content: center; align-items: center; }
        #slideshow-img { max-width: 100vw; max-height: 100vh; object-fit: contain; display: block; user-select: none; }
        #slideshow-hud { position: fixed; bottom: 0; left: 0; right: 0; background: linear-gradient(transparent, rgba(0,0,0,0.88)); padding: 48px 24px 18px; display: flex; align-items: center; gap: 8px; transition: opacity 0.4s; z-index: 2001; flex-wrap: wrap; }
        #ss-spacer { flex: 1; }
        #ss-counter { color: #bbb; font-size: 13px; min-width: 64px; text-align: center; }
        .ss-btn { background: rgba(255,255,255,0.15); color: white; border: none; border-radius: 8px; padding: 7px 12px; cursor: pointer; font-size: 14px; transition: background 0.2s; white-space: nowrap; line-height: 1.2; }
        .ss-btn:hover { background: rgba(255,255,255,0.3); }
        .ss-btn.ss-active { background: var(--accent); }
        .ss-sep { width: 1px; height: 28px; background: rgba(255,255,255,0.22); margin: 0 4px; align-self: center; flex-shrink: 0; }
        #ss-speed-select { background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.22); border-radius: 8px; padding: 7px 10px; font-size: 14px; cursor: pointer; }
        #ss-speed-select option { background: #2d2d2d; color: white; }
        #ss-scope-group, #ss-nav-group { display: flex; gap: 4px; }
    </style>
</head>
<body>
    <div id="gallery-container">
        <div id="breadcrumbs">
            <span id="breadcrumb-path"></span>
            <div id="search-container">
                <div id="search-bar">
                    <input id="search-input" type="text" placeholder="Name, tag, or description…"
                           onkeydown="if(event.key==='Enter') applySearch()" />
                    <button id="search-btn" onclick="applySearch()">Search</button>
                    <button id="search-close-btn" onclick="clearSearch()" title="Clear search">&times;</button>
                </div>
                <div id="search-toggle" onclick="toggleSearch()" title="Search photos">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                </div>
                <div id="slideshow-toggle" onclick="openSlideshow()" title="Slideshow">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                </div>
            </div>
        </div>
        <h3 class="section-title" id="folders-title">Folders</h3>
        <div class="grid" id="folders-grid"></div>
        <h3 class="section-title" id="images-title">Photos</h3>
        <div class="grid" id="images-grid"></div>
    </div>

    <div id="lightbox">
        <span id="close" onclick="closeLightbox()">&times;</span>
        <div id="prev" class="nav-btn" onclick="prevImage(event)">&#10094;</div>

        <div class="lightbox-content-wrapper">
            <div id="img-wrapper">
                <img id="lightbox-img" src="" alt="Fullscreen photo" />
                <div id="faces-container"></div>
            </div>
            <div id="metadata-panel">
                <div id="meta-description" class="meta-row"></div>
                <div id="meta-people" class="meta-row"></div>
                <div id="meta-tags" class="meta-row"></div>
            </div>
        </div>

        <div id="next" class="nav-btn" onclick="nextImage(event)">&#10095;</div>
    </div>

    <div id="slideshow-overlay">
        <img id="slideshow-img" src="" alt="Slideshow photo" />
        <div id="slideshow-hud">
            <div id="ss-scope-group">
                <button class="ss-btn ss-active" id="ss-scope-folder" onclick="setSsScope('folder')">This Folder</button>
                <button class="ss-btn" id="ss-scope-tree" onclick="setSsScope('tree')">+ Subfolders</button>
                <button class="ss-btn" id="ss-scope-all" onclick="setSsScope('all')">All</button>
            </div>
            <div class="ss-sep"></div>
            <div id="ss-nav-group">
                <button class="ss-btn" onclick="ssPrev()" title="Previous">&#10094;</button>
                <button class="ss-btn" id="ss-play-pause" onclick="toggleSsPlay()" title="Play / Pause">&#x23F8;</button>
                <button class="ss-btn" onclick="ssNext()" title="Next">&#10095;</button>
            </div>
            <span id="ss-counter">1 / 0</span>
            <div class="ss-sep"></div>
            <select id="ss-speed-select" onchange="setSsSpeed(parseInt(this.value))" title="Slide interval">
                <option value="1000">1 s</option>
                <option value="2000">2 s</option>
                <option value="3000">3 s</option>
                <option value="5000" selected>5 s</option>
                <option value="8000">8 s</option>
                <option value="15000">15 s</option>
                <option value="30000">30 s</option>
            </select>
            <button class="ss-btn" id="ss-random-btn" onclick="toggleSsRandom()" title="Shuffle / Sequential">&#x21C4; Shuffle</button>
            <div id="ss-spacer"></div>
            <button class="ss-btn" onclick="stopSlideshow()" title="Close slideshow">&#10005;</button>
        </div>
    </div>

    <script>
        const imagePaths = """

# imagePaths JSON array is injected here

_HTML_PART2 = r"""
        ;

        const rawMetadata = """

# rawMetadata JSON array is injected here

_HTML_PART3 = r"""
        ;

        function getOrientation(meta) {
            const o = getMeta(meta, 'Orientation');
            if (!o) return 1;
            if (typeof o === 'number') return o;
            if (o.includes('Rotate 90 CW'))  return 6;
            if (o.includes('Rotate 270 CW') || o.includes('90 CCW')) return 8;
            if (o.includes('Rotate 180'))    return 3;
            return 1;
        }

        function transformArea(area, orientation) {
            const {X, Y, W, H} = area;
            switch (orientation) {
                case 6: return {X: 1-Y, Y: X,   W: H, H: W};
                case 8: return {X: Y,   Y: 1-X, W: H, H: W};
                case 3: return {X: 1-X, Y: 1-Y, W: W, H: H};
                default: return area;
            }
        }

        function normalizePath(p) {
            return p.replace(/\\/g, '/').replace(/^[.\/]+/, '');
        }

        function getMeta(metaObj, keyName) {
            if (!metaObj) return null;
            for (let key in metaObj) {
                if (key === keyName || key.endsWith(':' + keyName)) return metaObj[key];
            }
            return null;
        }

        const metadataMap = {};
        if (Array.isArray(rawMetadata)) {
            rawMetadata.forEach(item => {
                if (item.SourceFile) {
                    metadataMap[normalizePath(item.SourceFile)] = item;
                }
            });
            console.log("Successfully loaded metadata for", Object.keys(metadataMap).length, "files.");
        }

        const fileTree = { "": { folders: new Set(), images: [] } };
        imagePaths.forEach(path => {
            const parts = path.split('/');
            const fileName = parts.pop();
            let currentPath = "";
            for (let i = 0; i < parts.length; i++) {
                const parentPath = currentPath;
                currentPath = currentPath ? currentPath + '/' + parts[i] : parts[i];
                if (!fileTree[currentPath]) fileTree[currentPath] = { folders: new Set(), images: [] };
                fileTree[parentPath].folders.add(currentPath);
            }
            if (!fileTree[currentPath]) fileTree[currentPath] = { folders: new Set(), images: [] };
            fileTree[currentPath].images.push({ name: fileName, path: path });
        });

        let currentImages = [];
        let currentImageIndex = 0;
        let currentFolderPath = '';

        function renderFolder(path) {
            const folderData = fileTree[path];
            if (!folderData) return;
            currentFolderPath = path;

            let breadcrumbHtml = `<span class="breadcrumb-link" onclick="renderFolder('')">Home</span>`;
            if (path !== "") {
                const parts = path.split('/');
                let buildPath = '';
                parts.forEach((part) => {
                    buildPath += (buildPath === '' ? part : '/' + part);
                    breadcrumbHtml += ' <span style="color:#888;">&rsaquo;</span> ';
                    breadcrumbHtml += `<span class="breadcrumb-link" onclick="renderFolder('${buildPath}')">${part}</span>`;
                });
            }
            document.getElementById('breadcrumb-path').innerHTML = breadcrumbHtml;

            const foldersGrid = document.getElementById('folders-grid');
            foldersGrid.innerHTML = '';
            const sortedFolders = Array.from(folderData.folders).sort();

            if (sortedFolders.length === 0) {
                document.getElementById('folders-title').style.display = 'none';
            } else {
                document.getElementById('folders-title').style.display = 'block';
                sortedFolders.forEach(subPath => {
                    const folderName = subPath.split('/').pop();
                    const folderDiv = document.createElement('div');
                    folderDiv.className = 'folder';
                    folderDiv.onclick = () => renderFolder(subPath);
                    folderDiv.innerHTML = `<svg viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg><div class="folder-name">${folderName}</div>`;
                    foldersGrid.appendChild(folderDiv);
                });
            }

            const imagesGrid = document.getElementById('images-grid');
            imagesGrid.innerHTML = '';
            currentImages = folderData.images.sort((a, b) => a.name.localeCompare(b.name));

            if (currentImages.length === 0) {
                document.getElementById('images-title').style.display = 'none';
            } else {
                document.getElementById('images-title').style.display = 'block';
                currentImages.forEach((imgObj, index) => {
                    const imgCard = document.createElement('div');
                    imgCard.className = 'image-card';
                    imgCard.onclick = () => openLightbox(index);
                    imgCard.innerHTML = `<img src="${encodeURI(imgObj.path)}" alt="${imgObj.name}" loading="lazy" />`;
                    imagesGrid.appendChild(imgCard);
                });
            }
        }

        const lightbox = document.getElementById('lightbox');
        const lightboxImg = document.getElementById('lightbox-img');
        const facesContainer = document.getElementById('faces-container');
        const btnPrev = document.getElementById('prev');
        const btnNext = document.getElementById('next');

        function openLightbox(index) {
            currentImageIndex = index;
            updateLightbox();
            lightbox.style.display = 'flex';
        }

        function closeLightbox() {
            lightbox.style.display = 'none';
            lightboxImg.src = '';
        }

        function updateLightbox() {
            const imgObj = currentImages[currentImageIndex];
            lightboxImg.src = encodeURI(imgObj.path);

            btnPrev.classList.toggle('disabled', currentImageIndex === 0);
            btnNext.classList.toggle('disabled', currentImageIndex === currentImages.length - 1);

            facesContainer.innerHTML = '';
            document.getElementById('meta-description').innerHTML = '';
            document.getElementById('meta-people').innerHTML = '';
            document.getElementById('meta-tags').innerHTML = '';

            const lookupPath = normalizePath(imgObj.path);
            const meta = metadataMap[lookupPath] || {};

            const description = getMeta(meta, 'Description') || getMeta(meta, 'Caption-Abstract') || getMeta(meta, 'UserComment') || '';
            const regionInfo = getMeta(meta, 'RegionInfo');
            const subjects = getMeta(meta, 'Subject');

            if (description) {
                document.getElementById('meta-description').innerHTML = `<span class="meta-label">Caption:</span> ${description}`;
            }

            let peopleNames = [];
            const orientation = getOrientation(meta);

            if (regionInfo && regionInfo.RegionList) {
                let regions = Array.isArray(regionInfo.RegionList) ? regionInfo.RegionList : [regionInfo.RegionList];

                regions.forEach(region => {
                    if ((region.Type === 'Face' || region.Type === 'Face|Face') && region.Area) {
                        if (region.Name) peopleNames.push(region.Name);

                        const a = transformArea(region.Area, orientation);
                        const leftPct = (a.X - (a.W / 2)) * 100;
                        const topPct  = (a.Y - (a.H / 2)) * 100;
                        const widthPct  = a.W * 100;
                        const heightPct = a.H * 100;

                        const faceDiv = document.createElement('div');
                        faceDiv.className = 'face-box';
                        faceDiv.style.left   = `${leftPct}%`;
                        faceDiv.style.top    = `${topPct}%`;
                        faceDiv.style.width  = `${widthPct}%`;
                        faceDiv.style.height = `${heightPct}%`;

                        const nameDiv = document.createElement('div');
                        nameDiv.className = 'face-name';
                        nameDiv.innerText = region.Name || 'Unknown';

                        faceDiv.appendChild(nameDiv);
                        facesContainer.appendChild(faceDiv);
                    }
                });
            }

            peopleNames = [...new Set(peopleNames)];
            if (peopleNames.length > 0) {
                document.getElementById('meta-people').innerHTML = `<span class="meta-label">People:</span> ${peopleNames.join(', ')}`;
            }

            if (subjects) {
                let tags = Array.isArray(subjects) ? subjects : [subjects];
                if (tags.length > 0) {
                    document.getElementById('meta-tags').innerHTML = `<span class="meta-label">Tags:</span> ${tags.join(', ')}`;
                }
            }
        }

        function prevImage(e) { if (e) e.stopPropagation(); if (currentImageIndex > 0) { currentImageIndex--; updateLightbox(); } }
        function nextImage(e) { if (e) e.stopPropagation(); if (currentImageIndex < currentImages.length - 1) { currentImageIndex++; updateLightbox(); } }

        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox || e.target.classList.contains('lightbox-content-wrapper')) closeLightbox();
        });

        function toggleSearch() {
            const bar = document.getElementById('search-bar');
            const toggle = document.getElementById('search-toggle');
            const isOpen = bar.classList.contains('open');
            if (isOpen) {
                clearSearch();
            } else {
                bar.classList.add('open');
                toggle.classList.add('active');
                document.getElementById('search-input').focus();
            }
        }

        function applySearch() {
            const query = document.getElementById('search-input').value.trim().toLowerCase();
            if (!query) { clearSearch(); return; }

            const results = imagePaths.filter(path => {
                const name = path.split('/').pop().toLowerCase();
                if (name.includes(query)) return true;

                const meta = metadataMap[normalizePath(path)] || {};
                const rawDesc = getMeta(meta, 'Description') || getMeta(meta, 'Caption-Abstract') || getMeta(meta, 'UserComment') || '';
                const description = (typeof rawDesc === 'string' ? rawDesc : '').toLowerCase();
                if (description.includes(query)) return true;

                const subjects = getMeta(meta, 'Subject');
                if (subjects) {
                    const tags = Array.isArray(subjects) ? subjects : [subjects];
                    if (tags.some(t => typeof t === 'string' && t.toLowerCase().includes(query))) return true;
                }

                const regionInfo = getMeta(meta, 'RegionInfo');
                if (regionInfo && regionInfo.RegionList) {
                    const regions = Array.isArray(regionInfo.RegionList) ? regionInfo.RegionList : [regionInfo.RegionList];
                    if (regions.some(r => r.Name && typeof r.Name === 'string' && r.Name.toLowerCase().includes(query))) return true;
                }

                return false;
            });

            document.getElementById('folders-title').style.display = 'none';
            document.getElementById('folders-grid').innerHTML = '';
            document.getElementById('images-title').style.display = 'none';
            document.getElementById('breadcrumb-path').innerHTML =
                `<span class="breadcrumb-link" onclick="clearSearch()">Home</span>` +
                ` <span style="color:#888;">&rsaquo;</span> ` +
                `Search: &ldquo;${query}&rdquo; ` +
                `<span style="color:#888; font-size:14px;">(${results.length} result${results.length !== 1 ? 's' : ''})</span>`;

            currentImages = results.map(path => ({ name: path.split('/').pop(), path }));
            const imagesGrid = document.getElementById('images-grid');
            imagesGrid.innerHTML = '';
            if (results.length === 0) {
                imagesGrid.innerHTML = '<p style="color:#888; grid-column:1/-1; margin:20px 0;">No photos matched your search.</p>';
            } else {
                currentImages.forEach((imgObj, index) => {
                    const imgCard = document.createElement('div');
                    imgCard.className = 'image-card';
                    imgCard.onclick = () => openLightbox(index);
                    imgCard.innerHTML = `<img src="${encodeURI(imgObj.path)}" alt="${imgObj.name}" loading="lazy" />`;
                    imagesGrid.appendChild(imgCard);
                });
            }
        }

        function clearSearch() {
            document.getElementById('search-bar').classList.remove('open');
            document.getElementById('search-toggle').classList.remove('active');
            document.getElementById('search-input').value = '';
            renderFolder(currentFolderPath);
        }

        // ── Slideshow ────────────────────────────────────────────────
        const ss = {
            images: [], index: 0, playing: true,
            speed: 5000, random: false, scope: 'folder',
            timer: null, hudTimer: null
        };

        function buildSlideshowImages() {
            if (ss.scope === 'all') {
                return imagePaths.map(p => ({ name: p.split('/').pop(), path: p }));
            }
            if (ss.scope === 'tree') {
                const prefix = currentFolderPath ? currentFolderPath + '/' : '';
                return imagePaths
                    .filter(p => currentFolderPath === '' ? true : p.startsWith(prefix))
                    .map(p => ({ name: p.split('/').pop(), path: p }));
            }
            // 'folder' — only direct images in the current folder
            const fd = fileTree[currentFolderPath];
            return fd ? fd.images.slice().sort((a, b) => a.name.localeCompare(b.name)) : [];
        }

        function openSlideshow() {
            ss.images = buildSlideshowImages();
            if (ss.images.length === 0) return;
            ss.index = 0;
            ss.playing = true;
            document.getElementById('slideshow-overlay').style.display = 'flex';
            updateSsImg();
            updateSsUI();
            scheduleSsAdvance();
            showSsHud();
        }

        function stopSlideshow() {
            ss.playing = false;
            clearTimeout(ss.timer);
            clearTimeout(ss.hudTimer);
            document.getElementById('slideshow-overlay').style.display = 'none';
            document.getElementById('slideshow-img').src = '';
        }

        function updateSsImg() {
            if (!ss.images.length) return;
            document.getElementById('slideshow-img').src = encodeURI(ss.images[ss.index].path);
            document.getElementById('ss-counter').textContent =
                (ss.index + 1) + ' / ' + ss.images.length;
        }

        function scheduleSsAdvance() {
            clearTimeout(ss.timer);
            if (ss.playing && ss.images.length > 1) {
                ss.timer = setTimeout(ssNext, ss.speed);
            }
        }

        function ssNext() {
            clearTimeout(ss.timer);
            if (!ss.images.length) return;
            ss.index = ss.random
                ? Math.floor(Math.random() * ss.images.length)
                : (ss.index + 1) % ss.images.length;
            updateSsImg();
            scheduleSsAdvance();
        }

        function ssPrev() {
            clearTimeout(ss.timer);
            if (!ss.images.length) return;
            ss.index = ss.random
                ? Math.floor(Math.random() * ss.images.length)
                : (ss.index - 1 + ss.images.length) % ss.images.length;
            updateSsImg();
            scheduleSsAdvance();
        }

        function toggleSsPlay() {
            ss.playing = !ss.playing;
            if (ss.playing) scheduleSsAdvance();
            else clearTimeout(ss.timer);
            updateSsUI();
        }

        function setSsSpeed(ms) {
            ss.speed = ms;
            scheduleSsAdvance();
        }

        function toggleSsRandom() {
            ss.random = !ss.random;
            updateSsUI();
        }

        function setSsScope(scope) {
            ss.scope = scope;
            ss.images = buildSlideshowImages();
            ss.index = 0;
            updateSsImg();
            updateSsUI();
            scheduleSsAdvance();
        }

        function updateSsUI() {
            document.getElementById('ss-play-pause').innerHTML = ss.playing ? '&#x23F8;' : '&#x25B6;';
            document.getElementById('ss-random-btn').classList.toggle('ss-active', ss.random);
            ['folder', 'tree', 'all'].forEach(s => {
                const el = document.getElementById('ss-scope-' + s);
                if (el) el.classList.toggle('ss-active', ss.scope === s);
            });
            document.getElementById('ss-counter').textContent = ss.images.length
                ? (ss.index + 1) + ' / ' + ss.images.length
                : '0 / 0';
        }

        function showSsHud() {
            const hud = document.getElementById('slideshow-hud');
            hud.style.opacity = '1';
            hud.style.pointerEvents = 'auto';
            clearTimeout(ss.hudTimer);
            ss.hudTimer = setTimeout(hideSsHud, 3500);
        }

        function hideSsHud() {
            const hud = document.getElementById('slideshow-hud');
            hud.style.opacity = '0';
            hud.style.pointerEvents = 'none';
        }

        const ssOverlay = document.getElementById('slideshow-overlay');
        const ssHud = document.getElementById('slideshow-hud');

        ssOverlay.addEventListener('mousemove', showSsHud);
        ssOverlay.addEventListener('click', (e) => {
            if (e.target === ssOverlay || e.target.id === 'slideshow-img') showSsHud();
        });
        // Keep HUD visible while hovering controls
        ssHud.addEventListener('mouseenter', () => clearTimeout(ss.hudTimer));
        ssHud.addEventListener('mouseleave', () => {
            ss.hudTimer = setTimeout(hideSsHud, 2000);
        });

        document.addEventListener('keydown', (e) => {
            if (ssOverlay.style.display === 'flex') {
                if (e.key === 'ArrowLeft')  { ssPrev(); showSsHud(); }
                if (e.key === 'ArrowRight') { ssNext(); showSsHud(); }
                if (e.key === ' ')          { e.preventDefault(); toggleSsPlay(); showSsHud(); }
                if (e.key === 'Escape')     stopSlideshow();
            } else if (lightbox.style.display === 'flex') {
                if (e.key === 'ArrowLeft')  prevImage();
                if (e.key === 'ArrowRight') nextImage();
                if (e.key === 'Escape')     closeLightbox();
            }
        });

        renderFolder("");
    </script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _check_exiftool() -> None:
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
    except FileNotFoundError:
        print("Error: 'exiftool' is not installed or not in PATH.", file=sys.stderr)
        print("Download it from https://exiftool.org", file=sys.stderr)
        _pause_if_gui_launch()
        sys.exit(1)


def _find_images(base_dir: Path) -> list:
    images = []
    for path in sorted(base_dir.rglob('*')):
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTENSIONS:
            # Always use forward slashes so the JS path tree works on all platforms
            relative = path.relative_to(base_dir).as_posix()
            images.append(relative)
    return images


def _get_metadata(base_dir: Path) -> list:
    result = subprocess.run(
        [
            'exiftool',
            '-ext', 'jpg', '-ext', 'jpeg', '-ext', 'png', '-ext', 'webp',
            '-r', '-json', '-q', '-struct',
            '-UserComment', '-Description', '-Caption-Abstract', '-Subject', '-RegionInfo', '-Orientation',
            '.',
        ],
        capture_output=True,
        text=True,
        cwd=str(base_dir),   # run from base_dir so SourceFile paths are relative
    )
    if result.stdout.strip():
        try:
            data = json.loads(result.stdout)
            # Normalise SourceFile to forward-slash relative paths (strip leading ./)
            for item in data:
                src = item.get('SourceFile', '')
                # exiftool with cwd outputs './Photos/img.jpg' — strip the './'
                if src.startswith('./') or src.startswith('.\\'):
                    item['SourceFile'] = src[2:].replace('\\', '/')
                else:
                    item['SourceFile'] = src.replace('\\', '/')
            return data
        except json.JSONDecodeError:
            print("Warning: could not parse exiftool output.", file=sys.stderr)
    return []


_DEFAULT_TITLE = 'Photo Gallery'
_DEFAULT_FOLDER_COLOR = '#F8D775'


def generate(base_dir: Path, output_path: Path, title: str = _DEFAULT_TITLE, folder_color: str = _DEFAULT_FOLDER_COLOR) -> None:
    _check_exiftool()
    print(f"Scanning {base_dir} …")

    images = _find_images(base_dir)
    print(f"  Found {len(images)} image(s).")

    print("  Running exiftool …")
    metadata = _get_metadata(base_dir)
    print(f"  Got metadata for {len(metadata)} file(s).")

    images_json   = json.dumps(images,   indent=8, ensure_ascii=False)
    metadata_json = json.dumps(metadata, indent=8, ensure_ascii=False) if metadata else '[]'

    html_part1 = _HTML_PART1.replace(
        f'<title>{_DEFAULT_TITLE}</title>',
        f'<title>{title}</title>',
    ).replace(
        f'fill: {_DEFAULT_FOLDER_COLOR}',
        f'fill: {folder_color}',
    )

    with output_path.open('w', encoding='utf-8') as fh:
        fh.write(html_part1)
        fh.write(images_json)
        fh.write(_HTML_PART2)
        fh.write(metadata_json)
        fh.write(_HTML_PART3)

    print(f"Gallery written to: {output_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate a self-contained HTML photo gallery.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Root directory to scan for images',
    )
    parser.add_argument(
        '-o', '--output',
        default='index.html',
        metavar='FILE',
        help='Output HTML file',
    )
    parser.add_argument(
        '-t', '--title',
        default=_DEFAULT_TITLE,
        metavar='TITLE',
        help='Gallery title shown in the browser tab',
    )
    parser.add_argument(
        '--folder-color',
        default=_DEFAULT_FOLDER_COLOR,
        metavar='COLOR',
        help='CSS color for folder icons (e.g. #F8D775 or cornflowerblue)',
    )
    args = parser.parse_args()

    base_dir = Path(args.directory).resolve()
    if not base_dir.is_dir():
        print(f"Error: '{base_dir}' is not a directory.", file=sys.stderr)
        _pause_if_gui_launch()
        sys.exit(1)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = base_dir / output_path

    generate(base_dir, output_path, title=args.title, folder_color=args.folder_color)


if __name__ == '__main__':
    main()
