// VideoSceneCaption.js
import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

console.log("=== VideoSceneCaption.js LOADING ===");

app.registerExtension({
    name: "VideoSceneCaption",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "VideoSceneCaption") {
            console.log("✓ VideoSceneCaption extension matched!");
            
            const originalNodeCreated = nodeType.prototype.onNodeCreated;
            const originalOnExecuted = nodeType.prototype.onExecuted;
            
            nodeType.prototype.onNodeCreated = function() {
                const result = originalNodeCreated?.apply(this, arguments);
                
                // Initialize properties
                this.sceneCaptions = [];
                this.sceneVideoPaths = [];
                this.sceneVideoUrls = [];
                this.currentSceneIndex = 0;
                this.totalScenes = 0;
                this.isModified = false;
                this.originalCaption = "";
                this.captionsDir = "";  // Will be set from onExecuted
                this.baseDir = "";      // Will be set from onExecuted
                
                // Find the selected_scene_index widget
                this.selectedSceneIndexWidget = this.widgets.find(w => w.name === "selected_scene_index");
                
                if (this.selectedSceneIndexWidget) {
                    const originalCallback = this.selectedSceneIndexWidget.callback;
                    const node = this;
                    
                    // Override callback to update preview when scene changes
                    this.selectedSceneIndexWidget.callback = function(value) {
                        if (originalCallback) originalCallback.call(this, value);
                        
                        const newIndex = Math.max(1, Math.min(value, node.totalScenes));
                        const oldIndex = node.currentSceneIndex;
                        node.currentSceneIndex = newIndex - 1;
                        
                        console.log(`Scene changed: ${oldIndex + 1} → ${newIndex}`);
                        
                        if (node.sceneCaptions.length > 0) {
                            node.updatePreview();
                        }
                    };
                }
                
                // Create preview UI
                this.createPreviewUI();
                return result;
            };
            
            nodeType.prototype.createPreviewUI = function() {
                // Create title section
                const titleDiv = document.createElement("div");
                titleDiv.style.cssText = `
                    font-weight: bold;
                    margin: 10px 0;
                    font-size: 14px;
                    color: #fff;
                    background: #444;
                    padding: 10px;
                    border-radius: 4px;
                    text-align: center;
                `;
                
                const titleText = document.createElement("div");
                titleText.textContent = "🎬 Video Scene Caption";
                titleText.style.marginBottom = "5px";
                
                const sceneCounter = document.createElement("div");
                sceneCounter.id = "caption-scene-counter";
                sceneCounter.style.cssText = `
                    font-size: 12px;
                    color: #aaa;
                    font-weight: normal;
                `;
                sceneCounter.textContent = "Use selected_scene_index to navigate";
                
                titleDiv.appendChild(titleText);
                titleDiv.appendChild(sceneCounter);
                
                const titleWidget = this.addDOMWidget("preview_title", "div", titleDiv);
                titleWidget.computeSize = () => [0, 65];
                this.sceneCounterElement = sceneCounter;
                
                // Create video preview container
                const videoContainer = document.createElement("div");
                videoContainer.style.cssText = `
                    background: #1a1a1a;
                    border-radius: 4px;
                    min-height: 180px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    padding: 10px;
                    margin: 10px 0;
                    position: relative;
                `;
                
                // Video element
                const videoElement = document.createElement("video");
                videoElement.style.cssText = `
                    max-width: 100%;
                    max-height: 280px;
                    border-radius: 4px;
                    display: none;
                `;
                videoElement.controls = true;
                videoElement.preload = "metadata";
                videoElement.playsInline = true;
                
                // Video placeholder
                const videoPlaceholder = document.createElement("div");
                videoPlaceholder.style.cssText = `
                    color: #666;
                    font-size: 14px;
                    font-style: italic;
                    text-align: center;
                    padding: 20px;
                `;
                videoPlaceholder.textContent = "No video loaded";
                
                // Video info display
                const videoInfo = document.createElement("div");
                videoInfo.style.cssText = `
                    font-size: 11px;
                    color: #888;
                    margin-top: 5px;
                    text-align: center;
                    font-family: monospace;
                    display: none;
                `;
                videoInfo.id = "video-info";
                
                videoContainer.appendChild(videoElement);
                videoContainer.appendChild(videoPlaceholder);
                videoContainer.appendChild(videoInfo);
                
                const videoWidget = this.addDOMWidget("video_preview", "div", videoContainer);
                videoWidget.computeSize = () => [0, 220];
                this.videoElement = videoElement;
                this.videoPlaceholder = videoPlaceholder;
                this.videoInfo = videoInfo;
                
                // Create caption textarea with label
                const captionContainer = document.createElement("div");
                captionContainer.style.cssText = `
                    margin: 10px 0;
                `;
                
                const captionLabel = document.createElement("div");
                captionLabel.style.cssText = `
                    font-size: 12px;
                    color: #aaa;
                    margin-bottom: 5px;
                    font-weight: bold;
                `;
                captionLabel.textContent = "Scene Description:";
                captionContainer.appendChild(captionLabel);
                
                const captionTextarea = document.createElement("textarea");
                captionTextarea.style.cssText = `
                    width: calc(100% - 20px);
                    min-height: 180px;
                    padding: 10px;
                    background: #2a2a2a;
                    color: #ddd;
                    border: 1px solid #444;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 12px;
                    resize: vertical;
                    line-height: 1.4;
                `;
                captionTextarea.value = "Run the node to generate captions";
                captionTextarea.addEventListener('input', () => {
                    this.isModified = captionTextarea.value !== this.originalCaption;
                    
                    // Update save button state
                    if (this.saveBtn) {
                        this.saveBtn.disabled = !this.isModified;
                        this.saveBtn.style.opacity = this.isModified ? "1" : "0.5";
                        this.saveBtn.style.cursor = this.isModified ? "pointer" : "not-allowed";
                    }
                });
                
                captionContainer.appendChild(captionTextarea);
                
                const captionWidget = this.addDOMWidget("caption_textarea", "div", captionContainer);
                captionWidget.computeSize = () => [0, 220];
                this.captionTextarea = captionTextarea;
                
                // Create save and clear buttons
                const buttonContainer = document.createElement("div");
                buttonContainer.style.cssText = `
                    display: flex;
                    gap: 10px;
                    margin-top: 10px;
                `;
                
                // Save button
                const saveBtn = document.createElement("button");
                saveBtn.textContent = "💾 Save Description";
                saveBtn.style.cssText = `
                    flex: 1;
                    height: 35px;
                    background: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: not-allowed;
                    font-size: 13px;
                    font-weight: bold;
                    opacity: 0.5;
                `;
                saveBtn.disabled = true;
                saveBtn.onclick = () => {
                    console.log("Save button clicked");
                    this.saveDescription();
                };
                
                // Clear button
                const clearBtn = document.createElement("button");
                clearBtn.textContent = "🗑️ Clear";
                clearBtn.style.cssText = `
                    flex: 1;
                    height: 35px;
                    background: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 13px;
                    font-weight: bold;
                `;
                clearBtn.onclick = () => {
                    console.log("Clear button clicked");
                    this.clearDescription();
                };
                
                buttonContainer.appendChild(saveBtn);
                buttonContainer.appendChild(clearBtn);
                
                const buttonWidget = this.addDOMWidget("caption_buttons", "div", buttonContainer);
                buttonWidget.computeSize = () => [0, 45];
                this.saveBtn = saveBtn;
                this.clearBtn = clearBtn;
            };
            
            nodeType.prototype.onExecuted = function(message) {
                if (originalOnExecuted) originalOnExecuted.apply(this, arguments);
                
                console.log("=== VideoSceneCaption DEBUG ===");
                
                // Get scene captions
                if (message?.scene_captions) {
                    this.sceneCaptions = Array.isArray(message.scene_captions[0]) 
                        ? message.scene_captions[0] 
                        : message.scene_captions || [];
                    this.totalScenes = this.sceneCaptions.length;
                    console.log(`Total scenes (captions): ${this.totalScenes}`);
                }
                
                // Get video paths
                if (message?.scene_video_paths) {
                    this.sceneVideoPaths = Array.isArray(message.scene_video_paths[0])
                        ? message.scene_video_paths[0]
                        : message.scene_video_paths || [];
                    console.log(`Total video paths: ${this.sceneVideoPaths.length}`);
                }
                
                // Get video URLs
                if (message?.scene_video_urls) {
                    this.sceneVideoUrls = Array.isArray(message.scene_video_urls[0])
                        ? message.scene_video_urls[0]
                        : message.scene_video_urls || [];
                    console.log(`Total video URLs: ${this.sceneVideoUrls.length}`);
                }
                
                // Get captions directory - IMPORTANT FIX
                if (message?.captions_dir) {
                    this.captionsDir = Array.isArray(message.captions_dir)
                        ? message.captions_dir[0]
                        : message.captions_dir;
                    console.log(`Captions directory: ${this.captionsDir}`);
                }
                
                // Get base directory
                if (message?.base_dir) {
                    this.baseDir = Array.isArray(message.base_dir)
                        ? message.base_dir[0]
                        : message.base_dir;
                    console.log(`Base directory: ${this.baseDir}`);
                }
                
                // Get selected index
                if (message?.selected_index) {
                    this.currentSceneIndex = (message.selected_index[0] || message.selected_index || 1) - 1;
                }
                
                console.log(`Current scene index (0-based): ${this.currentSceneIndex}`);
                console.log(`Current scene number (1-based): ${this.currentSceneIndex + 1}`);
                
                // Update widget max value
                if (this.selectedSceneIndexWidget && this.totalScenes > 0) {
                    this.selectedSceneIndexWidget.options.max = this.totalScenes;
                    if (this.selectedSceneIndexWidget.value > this.totalScenes) {
                        this.selectedSceneIndexWidget.value = this.totalScenes;
                        if (this.selectedSceneIndexWidget.callback) {
                            this.selectedSceneIndexWidget.callback(this.totalScenes);
                        }
                    }
                    console.log(`Updated selected_scene_index max to: ${this.totalScenes}`);
                }
                
                // Update preview if we have data
                if (this.sceneCaptions.length > 0) {
                    console.log("Calling updatePreview...");
                    this.updatePreview();
                } else {
                    console.log("No captions to display");
                    this.captionTextarea.value = "No captions generated yet";
                    this.captionTextarea.style.color = "#f55";
                }
                
                console.log("=== END DEBUG ===");
            };
            
            nodeType.prototype.updatePreview = function() {
                const idx = this.currentSceneIndex;
                console.log(`=== updatePreview for scene ${idx + 1} ===`);
                
                // Update scene counter
                if (this.sceneCounterElement) {
                    this.sceneCounterElement.textContent = `Scene ${idx + 1} of ${this.totalScenes}`;
                    if (this.totalScenes > 0) {
                        this.sceneCounterElement.style.color = "#4af";
                    }
                }
                
                // Load video for current scene
                if (this.sceneVideoUrls.length > idx && this.sceneVideoUrls[idx]) {
                    const videoUrl = this.sceneVideoUrls[idx];
                    console.log(`Loading video URL for scene ${idx + 1}: ${videoUrl}`);
                    this.loadVideo(videoUrl);
                } else if (this.sceneVideoPaths.length > idx) {
                    const videoPath = this.sceneVideoPaths[idx];
                    console.log(`No URL available, falling back to path: ${videoPath}`);
                    this.loadVideo(videoPath);
                } else {
                    console.log(`No video available for scene ${idx + 1}`);
                    this.showNoVideo(`No video for scene ${idx + 1}`);
                }
                
                // Load caption for current scene
                if (this.sceneCaptions.length > idx) {
                    const caption = this.sceneCaptions[idx];
                    console.log(`Caption for scene ${idx + 1} (${caption.length} chars)`);
                    
                    this.captionTextarea.value = caption;
                    this.originalCaption = caption;
                    this.isModified = false;
                    
                    // Reset save button state
                    if (this.saveBtn) {
                        this.saveBtn.disabled = true;
                        this.saveBtn.style.opacity = "0.5";
                        this.saveBtn.style.cursor = "not-allowed";
                    }
                    
                    // Update textarea style based on content
                    if (caption.length > 1000) {
                        this.captionTextarea.style.height = "250px";
                    } else if (caption.length > 500) {
                        this.captionTextarea.style.height = "200px";
                    } else if (caption.length > 200) {
                        this.captionTextarea.style.height = "180px";
                    } else {
                        this.captionTextarea.style.height = "150px";
                    }
                    
                    // Reset text color
                    this.captionTextarea.style.color = "#ddd";
                } else {
                    console.log(`No caption for scene ${idx + 1}`);
                    this.captionTextarea.value = `No caption available for scene ${idx + 1}`;
                    this.captionTextarea.style.color = "#f55";
                    this.originalCaption = "";
                    this.isModified = false;
                }
            };
            
            nodeType.prototype.loadVideo = function(videoUrlOrPath) {
                console.log(`=== loadVideo called ===`);
                console.log(`Input: ${videoUrlOrPath}`);
                
                if (!videoUrlOrPath || videoUrlOrPath.trim() === "") {
                    console.log(`ERROR: Empty video path`);
                    this.showNoVideo("Empty video path");
                    return;
                }
                
                // Clean and encode the path if it's not already a URL
                let finalUrl = videoUrlOrPath;
                
                // If it looks like a local path and doesn't start with /
                if (!videoUrlOrPath.startsWith('/') && 
                    (videoUrlOrPath.includes('\\') || /^[A-Za-z]:/.test(videoUrlOrPath))) {
                    
                    const encodedPath = encodeURIComponent(videoUrlOrPath.trim());
                    finalUrl = `/video_scene/viewer/read_video?filepath=${encodedPath}`;
                    console.log(`Converted local path to URL: ${finalUrl}`);
                }
                
                // Reset video element
                this.videoElement.src = "";
                this.videoElement.style.display = "none";
                this.videoPlaceholder.style.display = "block";
                this.videoPlaceholder.textContent = "Loading video...";
                this.videoPlaceholder.style.color = "#4af";
                this.videoInfo.style.display = "none";
                
                console.log(`Loading from URL: ${finalUrl}`);
                this.videoElement.src = finalUrl;
                this.videoElement.style.display = "block";
                this.videoPlaceholder.style.display = "none";
                
                // Add debug event listeners
                this.videoElement.onloadeddata = () => {
                    console.log(`✓ Video loaded successfully`);
                    console.log(`  URL: ${finalUrl}`);
                    console.log(`  Dimensions: ${this.videoElement.videoWidth}x${this.videoElement.videoHeight}`);
                    console.log(`  Duration: ${this.videoElement.duration}s`);
                    
                    this.videoInfo.textContent = `${this.videoElement.videoWidth}x${this.videoElement.videoHeight} | ${this.videoElement.duration.toFixed(1)}s`;
                    this.videoInfo.style.display = "block";
                    this.videoInfo.style.color = "#4af";
                };
                
                this.videoElement.onerror = (error) => {
                    console.log(`✗ Failed to load video`);
                    console.log(`  URL: ${finalUrl}`);
                    console.log(`  Error:`, error);
                    console.log(`  Video error code: ${this.videoElement.error?.code}`);
                    
                    this.showNoVideo(`Failed to load: ${this.videoElement.error?.message || 'Unknown error'}`);
                };
            };
            
            nodeType.prototype.showNoVideo = function(reason = "") {
                console.log(`showNoVideo: ${reason}`);
                this.videoElement.style.display = "none";
                this.videoPlaceholder.style.display = "block";
                this.videoPlaceholder.textContent = reason || "Video not available";
                this.videoPlaceholder.style.color = "#f55";
                this.videoInfo.style.display = "none";
            };
            
            nodeType.prototype.saveDescription = async function() {
                console.log("=== saveDescription START ===");
                
                if (!this.isModified || !this.captionTextarea) {
                    alert("No changes to save");
                    return;
                }
                
                const newDescription = this.captionTextarea.value;
                const sceneIndex = this.currentSceneIndex;
                
                console.log(`Saving description for scene ${sceneIndex + 1}`);
                console.log(`Captions directory: ${this.captionsDir}`);
                
                // Construct the filename
                const filename = `scene_${sceneIndex.toString().padStart(4, '0')}_caption.txt`;
                
                // Construct full filepath
                let captionFilepath;
                if (this.captionsDir) {
                    // Use forward slashes for consistency
                    captionFilepath = `${this.captionsDir}/${filename}`.replace(/\\/g, '/');
                    console.log(`Using captions_dir: ${captionFilepath}`);
                } else {
                    console.error("ERROR: No captions directory available!");
                    alert("Error: Cannot determine save location. Please run the node first.");
                    return;
                }
                
                try {
                    console.log(`Sending save request...`);
                    console.log(`  Filepath: ${captionFilepath}`);
                    console.log(`  Content length: ${newDescription.length} chars`);
                    
                    const response = await api.fetchApi("/video_scene/viewer/save_description", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            filepath: captionFilepath,
                            content: newDescription
                        })
                    });
                    
                    console.log(`Response status: ${response.status}`);
                    
                    if (response.ok) {
                        const result = await response.json();
                        console.log("✓ Save successful:", result);
                        
                        // Update local state
                        this.originalCaption = newDescription;
                        this.isModified = false;
                        this.saveBtn.disabled = true;
                        this.saveBtn.style.opacity = "0.5";
                        this.saveBtn.style.cursor = "not-allowed";
                        
                        // Update the sceneCaptions array
                        if (sceneIndex < this.sceneCaptions.length) {
                            this.sceneCaptions[sceneIndex] = newDescription;
                        }
                        
                        alert(`✓ Caption saved successfully!\n\nFile: ${filename}\nLocation: ${result.directory || this.captionsDir}`);
                        
                    } else {
                        const errorText = await response.text();
                        console.error("✗ Save failed:", errorText);
                        alert("Error saving caption:\n" + errorText);
                    }
                } catch (error) {
                    console.error("✗ Save error:", error);
                    alert("Error saving caption:\n" + error.message);
                }
                
                console.log("=== saveDescription END ===");
            };
            
            nodeType.prototype.clearDescription = function() {
                if (this.captionTextarea && confirm("Clear description? This cannot be undone.")) {
                    this.captionTextarea.value = "";
                    this.isModified = true;
                    
                    // Update save button state
                    if (this.saveBtn) {
                        this.saveBtn.disabled = false;
                        this.saveBtn.style.opacity = "1";
                        this.saveBtn.style.cursor = "pointer";
                    }
                }
            };
        }
    }
});

console.log("=== VideoSceneCaption.js LOADED ===");