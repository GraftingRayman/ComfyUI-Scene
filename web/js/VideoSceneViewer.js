import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

console.log("=== VideoSceneViewer.js LOADING ===");

app.registerExtension({
    name: "VideoSceneViewerExtension",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        console.log("beforeRegisterNodeDef called for:", nodeData.name);
        
        if (nodeData.name === "VideoSceneViewer") {
            console.log("✓ VideoSceneViewer extension matched!");
            
            const originalNodeCreated = nodeType.prototype.onNodeCreated;
            const originalOnExecuted = nodeType.prototype.onExecuted;
            
            nodeType.prototype.onNodeCreated = function() {
                console.log("=== onNodeCreated START ===");
                const result = originalNodeCreated?.apply(this, arguments);
                
                // Initialize state
                this.sceneFilenames = [];
                this.scenePaths = [];
                this.sceneBasenames = [];
                this.txtPaths = [];
                this.currentSceneIndex = 0;
                this.totalScenes = 0;
                this.isDescriptionModified = false;
                this.originalDescription = "";
                this.currentDirectory = "";
                
                // Find widgets
                this.sceneDescriptionWidget = this.widgets.find(w => w.name === "scene_description");
                this.selectedSceneIndexWidget = this.widgets.find(w => w.name === "selected_scene_index");
                this.sceneDirectoryWidget = this.widgets.find(w => w.name === "scene_directory");
                
                console.log("Found widgets:", {
                    descriptionWidget: !!this.sceneDescriptionWidget,
                    indexWidget: !!this.selectedSceneIndexWidget,
                    directoryWidget: !!this.sceneDirectoryWidget
                });
                
                // Hide scene_description widget (handled by our UI)
                if (this.sceneDescriptionWidget && this.sceneDescriptionWidget.inputEl) {
                    this.sceneDescriptionWidget.inputEl.style.display = "none";
                }
                
                // Hook into selected_scene_index widget callback
                if (this.selectedSceneIndexWidget) {
                    const originalCallback = this.selectedSceneIndexWidget.callback;
                    const node = this;
                    
                    this.selectedSceneIndexWidget.callback = function(value) {
                        console.log("🔄 selected_scene_index changed to:", value);
                        
                        if (originalCallback) {
                            originalCallback.call(this, value);
                        }
                        
                        const newIndex = Math.max(0, Math.min(value - 1, node.totalScenes - 1));
                        console.log("  Old index:", node.currentSceneIndex, "New index:", newIndex);
                        
                        if (newIndex !== node.currentSceneIndex) {
                            node.currentSceneIndex = newIndex;
                            
                            if (node.scenePaths.length > 0) {
                                console.log("  Triggering updatePreview due to index change");
                                node.updatePreview();
                            }
                        }
                    };
                }
                
                // Create preview UI
                this.createPreviewUI();
                
                console.log("=== onNodeCreated END ===");
                return result;
            };
            
            nodeType.prototype.createPreviewUI = function() {
                console.log("=== createPreviewUI START ===");
                
                // Title section
                const titleDiv = document.createElement("div");
                titleDiv.style.cssText = `
                    font-weight: bold;
                    margin: 10px 0;
                    font-size: 14px;
                    color: #fff;
                    background: #1a1a1a;
                    padding: 10px;
                    border-radius: 4px;
                    text-align: center;
                `;
                
                const titleText = document.createElement("div");
                titleText.textContent = "🎬 Scene Viewer";
                titleText.style.marginBottom = "5px";
                
                const sceneCounter = document.createElement("div");
                sceneCounter.id = "scene-counter";
                sceneCounter.style.cssText = `
                    font-size: 12px;
                    color: #888;
                    font-weight: normal;
                `;
                sceneCounter.textContent = "Execute node to load scenes";
                
                titleDiv.appendChild(titleText);
                titleDiv.appendChild(sceneCounter);
                
                this.addDOMWidget("preview_title", "div", titleDiv).computeSize = () => [0, 65];
                this.sceneCounterElement = sceneCounter;
                
                // Directory info
                const dirInfoDiv = document.createElement("div");
                dirInfoDiv.style.cssText = `
                    font-size: 11px;
                    color: #aaa;
                    margin: 5px 0;
                    padding: 5px;
                    background: #2a2a2a;
                    border-radius: 3px;
                    word-break: break-all;
                `;
                dirInfoDiv.id = "directory-info";
                dirInfoDiv.textContent = "No directory loaded";
                
                this.addDOMWidget("dir_info", "div", dirInfoDiv).computeSize = () => [0, 35];
                this.dirInfoElement = dirInfoDiv;
                
                // Image container
                const imageContainer = document.createElement("div");
                imageContainer.style.cssText = `
                    background: #0a0a0a;
                    border-radius: 4px;
                    min-height: 200px;
                    max-height: 450px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 10px;
                    margin: 10px 0;
                    overflow: hidden;
                `;
                
                const imageElement = document.createElement("img");
                imageElement.id = "scene-preview-image";
                imageElement.style.cssText = `
                    max-width: 100%;
                    max-height: 100%;
                    width: auto;
                    height: auto;
                    object-fit: contain;
                    border-radius: 4px;
                    display: none;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                `;
                
                const imagePlaceholder = document.createElement("div");
                imagePlaceholder.style.cssText = `
                    color: #666;
                    font-size: 14px;
                    font-style: italic;
                `;
                imagePlaceholder.textContent = "No scene loaded";
                
                imageContainer.appendChild(imageElement);
                imageContainer.appendChild(imagePlaceholder);
                
                this.addDOMWidget("preview_image", "div", imageContainer).computeSize = () => [0, 470];
                this.imageElement = imageElement;
                this.imagePlaceholder = imagePlaceholder;
                
                // Description label
                const descLabel = document.createElement("div");
                descLabel.textContent = "Description:";
                descLabel.style.cssText = `
                    font-weight: bold;
                    margin: 10px 0 5px 0;
                    font-size: 12px;
                    color: #ccc;
                `;
                
                this.addDOMWidget("desc_label", "div", descLabel).computeSize = () => [0, 25];
                
                // Description textarea
                const descTextarea = document.createElement("textarea");
                descTextarea.style.cssText = `
                    width: calc(100% - 20px);
                    min-height: 132px;
                    padding: 10px;
                    background: #2a2a2a;
                    color: #ddd;
                    border: 1px solid #444;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 11px;
                    resize: vertical;
                `;
                descTextarea.value = "Execute node to load description";
                
                descTextarea.addEventListener('input', () => {
                    this.isDescriptionModified = descTextarea.value !== this.originalDescription;
                    console.log("Description modified:", this.isDescriptionModified);
                    
                    if (this.saveDescBtn) {
                        this.saveDescBtn.disabled = !this.isDescriptionModified;
                        this.saveDescBtn.style.opacity = this.isDescriptionModified ? "1" : "0.5";
                    }
                    
                    // Update widget value
                    if (this.sceneDescriptionWidget) {
                        this.sceneDescriptionWidget.value = descTextarea.value;
                    }
                });
                
                this.addDOMWidget("desc_textarea", "textarea", descTextarea).computeSize = () => [0, 154];
                this.descriptionTextarea = descTextarea;
                
                // Buttons
                const buttonContainer = document.createElement("div");
                buttonContainer.style.cssText = `
                    display: flex;
                    gap: 10px;
                    margin-top: 10px;
                `;
                
                const saveDescBtn = document.createElement("button");
                saveDescBtn.textContent = "💾 Save";
                saveDescBtn.style.cssText = `
                    flex: 1;
                    height: 35px;
                    background: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 13px;
                    font-weight: bold;
                    opacity: 0.5;
                `;
                saveDescBtn.disabled = true;
                saveDescBtn.onclick = () => this.saveDescription();
                
                const clearDescBtn = document.createElement("button");
                clearDescBtn.textContent = "🗑️ Clear";
                clearDescBtn.style.cssText = `
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
                clearDescBtn.onclick = () => this.clearDescription();
                
                buttonContainer.appendChild(saveDescBtn);
                buttonContainer.appendChild(clearDescBtn);
                
                this.addDOMWidget("desc_buttons", "div", buttonContainer).computeSize = () => [0, 45];
                this.saveDescBtn = saveDescBtn;
                this.clearDescBtn = clearDescBtn;
                
                console.log("✓ Preview UI created");
                console.log("=== createPreviewUI END ===");
            };
            
            nodeType.prototype.onExecuted = function(message) {
                console.log("=== onExecuted START ===");
                console.log("Message received:", JSON.stringify(message, null, 2));
                
                if (originalOnExecuted) {
                    originalOnExecuted.apply(this, arguments);
                }
                
                if (!message) {
                    console.log("❌ No message received");
                    return;
                }
                
                // Get UI data from message
                const uiData = message.ui || message;
                console.log("UI Data:", uiData);
                
                // Extract data
                if (uiData.scene_filenames && uiData.scene_filenames[0]) {
                    this.sceneFilenames = uiData.scene_filenames[0];
                    console.log("Loaded scene filenames:", this.sceneFilenames.length);
                }
                
                if (uiData.scene_paths && uiData.scene_paths[0]) {
                    this.scenePaths = uiData.scene_paths[0];
                    console.log("Loaded scene paths:", this.scenePaths.length);
                    console.log("First path:", this.scenePaths[0]);
                }
                
                if (uiData.scene_basenames && uiData.scene_basenames[0]) {
                    this.sceneBasenames = uiData.scene_basenames[0];
                }
                
                if (uiData.txt_paths && uiData.txt_paths[0]) {
                    this.txtPaths = uiData.txt_paths[0];
                    console.log("Loaded txt paths:", this.txtPaths.length);
                    console.log("First txt path:", this.txtPaths[0]);
                }
                
                if (uiData.total_scenes && uiData.total_scenes[0]) {
                    this.totalScenes = uiData.total_scenes[0];
                } else {
                    this.totalScenes = this.scenePaths.length;
                }
                
                if (uiData.directory && uiData.directory[0]) {
                    this.currentDirectory = uiData.directory[0];
                    if (this.dirInfoElement) {
                        const shortDir = this.currentDirectory.length > 60 ? 
                            "..." + this.currentDirectory.slice(-60) : this.currentDirectory;
                        this.dirInfoElement.textContent = `Directory: ${shortDir}`;
                        this.dirInfoElement.title = this.currentDirectory;
                    }
                }
                
                let selectedIndex = 1;
                if (uiData.selected_index && uiData.selected_index[0]) {
                    selectedIndex = uiData.selected_index[0];
                }
                
                console.log("Selected index from server:", selectedIndex);
                
                // Update widget
                if (this.selectedSceneIndexWidget) {
                    this.selectedSceneIndexWidget.value = selectedIndex;
                    this.selectedSceneIndexWidget.options.max = this.totalScenes;
                }
                
                this.currentSceneIndex = Math.max(0, Math.min(selectedIndex - 1, this.totalScenes - 1));
                console.log("Set currentSceneIndex to:", this.currentSceneIndex);
                
                // Get description
                if (uiData.text && uiData.text[0]) {
                    const description = uiData.text[0];
                    console.log("Received description, length:", description.length);
                    console.log("First 100 chars:", description.substring(0, 100));
                    
                    if (this.descriptionTextarea) {
                        this.descriptionTextarea.value = description;
                        this.originalDescription = description;
                        this.isDescriptionModified = false;
                        console.log("Set textarea value");
                    }
                    
                    if (this.sceneDescriptionWidget) {
                        this.sceneDescriptionWidget.value = description;
                        console.log("Set widget value");
                    }
                    
                    if (this.saveDescBtn) {
                        this.saveDescBtn.disabled = true;
                        this.saveDescBtn.style.opacity = "0.5";
                    }
                }
                
                // Update UI
                if (this.sceneCounterElement) {
                    this.sceneCounterElement.textContent = `Scene ${selectedIndex} of ${this.totalScenes}`;
                }
                
                // Update preview if we have scenes
                if (this.scenePaths.length > 0) {
                    console.log(`Updating preview with ${this.scenePaths.length} scenes`);
                    this.updatePreview();
                } else {
                    console.log("❌ No scenes to preview");
                    if (this.imagePlaceholder) {
                        this.imagePlaceholder.textContent = "No scenes found";
                    }
                }
                
                console.log("=== onExecuted END ===");
            };
            
            nodeType.prototype.updatePreview = async function() {
                console.log("=== updatePreview START ===");
                console.log("Current scene index:", this.currentSceneIndex);
                console.log("Total scenes:", this.scenePaths.length);
                
                if (!this.scenePaths || this.scenePaths.length === 0) {
                    console.log("❌ No scenes to update");
                    return;
                }
                
                if (this.currentSceneIndex >= this.scenePaths.length) {
                    console.log("❌ Invalid scene index:", this.currentSceneIndex);
                    return;
                }
                
                const imagePath = this.scenePaths[this.currentSceneIndex];
                const txtPath = this.txtPaths[this.currentSceneIndex];
                
                console.log("Loading scene:");
                console.log("  Image:", imagePath);
                console.log("  Text:", txtPath);
                
                // Load image via secured API endpoint
                try {
                    const imageUrl = `/video_scene/viewer/read_image?filepath=${encodeURIComponent(imagePath)}&t=${Date.now()}`;
                    console.log("📡 Fetching image:", imageUrl);
                    
                    const response = await fetch(imageUrl);
                    console.log("Image response status:", response.status);
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const objectUrl = URL.createObjectURL(blob);
                        
                        this.imageElement.onload = () => {
                            console.log("✓ Image loaded into DOM");
                        };
                        
                        this.imageElement.onerror = (err) => {
                            console.error("❌ Error loading image into DOM:", err);
                            this.showImageError("Failed to display image");
                        };
                        
                        this.imageElement.src = objectUrl;
                        this.imageElement.style.display = "block";
                        this.imagePlaceholder.style.display = "none";
                        
                        // Clean up
                        setTimeout(() => URL.revokeObjectURL(objectUrl), 10000);
                    } else {
                        const errorText = await response.text();
                        console.error("❌ Image load failed:", errorText);
                        this.showImageError(`API Error: ${errorText}`);
                    }
                } catch (error) {
                    console.error("❌ Error loading image:", error);
                    this.showImageError(`Network Error: ${error.message}`);
                }
                
                // Load description via secured API endpoint
                if (txtPath) {
                    try {
                        const descUrl = `/video_scene/viewer/read_description?filepath=${encodeURIComponent(txtPath)}&t=${Date.now()}`;
                        console.log("📡 Fetching description:", descUrl);
                        
                        const response = await fetch(descUrl);
                        console.log("Description response status:", response.status);
                        
                        if (response.ok) {
                            const description = await response.text();
                            console.log("✓ Loaded description, length:", description.length);
                            console.log("First 100 chars:", description.substring(0, 100));
                            
                            // Always update with fresh description
                            this.descriptionTextarea.value = description;
                            this.originalDescription = description;
                            this.isDescriptionModified = false;
                            
                            if (this.sceneDescriptionWidget) {
                                this.sceneDescriptionWidget.value = description;
                            }
                            
                            if (this.saveDescBtn) {
                                this.saveDescBtn.disabled = true;
                                this.saveDescBtn.style.opacity = "0.5";
                            }
                        } else {
                            const errorText = await response.text();
                            console.error("❌ Description load failed:", errorText);
                        }
                    } catch (error) {
                        console.error("❌ Error loading description via API:", error);
                    }
                } else {
                    console.log("❌ No txt path for current scene");
                }
                
                console.log("=== updatePreview END ===");
            };
            
            nodeType.prototype.showImageError = function(message) {
                this.imageElement.style.display = "none";
                this.imagePlaceholder.style.display = "block";
                this.imagePlaceholder.textContent = message;
                if (this.saveDescBtn) {
                    this.saveDescBtn.disabled = true;
                    this.saveDescBtn.style.opacity = "0.5";
                }
            };
            
            nodeType.prototype.saveDescription = async function() {
                if (!this.descriptionTextarea || this.txtPaths.length === 0) {
                    alert("No description to save");
                    return;
                }
                
                const txtPath = this.txtPaths[this.currentSceneIndex];
                const content = this.descriptionTextarea.value;
                
                console.log("💾 Saving description to:", txtPath);
                console.log("Content length:", content.length);
                
                try {
                    const response = await api.fetchApi("/video_scene/viewer/save_description", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            filepath: txtPath,
                            content: content
                        })
                    });
                    
                    console.log("Save response status:", response.status);
                    
                    if (response.ok) {
                        const result = await response.json();
                        alert(result.message || "Description saved!");
                        
                        this.originalDescription = content;
                        this.isDescriptionModified = false;
                        this.saveDescBtn.disabled = true;
                        this.saveDescBtn.style.opacity = "0.5";
                        
                        if (this.sceneDescriptionWidget) {
                            this.sceneDescriptionWidget.value = content;
                        }
                        
                        console.log("✓ Description saved");
                    } else {
                        const errorText = await response.text();
                        alert("Error: " + errorText);
                        console.error("❌ Save failed:", errorText);
                    }
                } catch (error) {
                    console.error("❌ Save error:", error);
                    alert("Error: " + error.message);
                }
            };
            
            nodeType.prototype.clearDescription = function() {
                if (this.descriptionTextarea && confirm("Clear description?")) {
                    this.descriptionTextarea.value = "";
                    this.isDescriptionModified = true;
                    this.saveDescBtn.disabled = false;
                    this.saveDescBtn.style.opacity = "1";
                    
                    if (this.sceneDescriptionWidget) {
                        this.sceneDescriptionWidget.value = "";
                    }
                }
            };
            
            console.log("✓ VideoSceneViewer extension registered");
        }
    }
});

console.log("=== VideoSceneViewer.js LOADED ===");