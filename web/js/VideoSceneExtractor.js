import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";
import { ComfyWidgets } from "/scripts/widgets.js";

console.log("=== VideoSceneExtractor.js LOADING ===");

app.registerExtension({
    name: "VideoSceneViewer",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        console.log("beforeRegisterNodeDef called for:", nodeData.name);
        
        if (nodeData.name === "VideoSceneGenerationNode") {
            console.log("✓ VideoSceneGenerationNode extension matched!");
            
            const originalNodeCreated = nodeType.prototype.onNodeCreated;
            const originalOnExecuted = nodeType.prototype.onExecuted;
            
            nodeType.prototype.onNodeCreated = function() {
                console.log("=== onNodeCreated START ===");
                const result = originalNodeCreated?.apply(this, arguments);
                
                console.log("Node widgets:", this.widgets?.map(w => w.name));
                
                // Initialize state
                this.scenePaths = [];
                this.currentSceneIndex = 0;
                this.totalScenes = 0;
                this.isDescriptionModified = false;
                this.originalDescription = "";
                
                // Find widgets
                this.sceneDescriptionWidget = this.widgets.find(w => w.name === "scene_description");
                this.selectedSceneIndexWidget = this.widgets.find(w => w.name === "selected_scene_index");
                
                console.log("scene_description widget found:", !!this.sceneDescriptionWidget);
                console.log("selected_scene_index widget found:", !!this.selectedSceneIndexWidget);
                
                // Hide scene_description widget
                if (this.sceneDescriptionWidget) {
                    this.sceneDescriptionWidget.computeSize = () => [0, -4];
                    if (this.sceneDescriptionWidget.inputEl) {
                        this.sceneDescriptionWidget.inputEl.style.display = "none";
                    }
                }
                
                // Hook into selected_scene_index widget callback
                if (this.selectedSceneIndexWidget) {
                    const originalCallback = this.selectedSceneIndexWidget.callback;
                    const node = this;
                    
                    this.selectedSceneIndexWidget.callback = function(value) {
                        console.log("selected_scene_index changed to:", value);
                        
                        // Call original callback if it exists
                        if (originalCallback) {
                            originalCallback.call(this, value);
                        }
                        
                        // Update the preview when index changes
                        const newIndex = Math.max(1, Math.min(value, node.totalScenes));
                        node.currentSceneIndex = newIndex - 1; // Convert 1-based to 0-based
                        
                        console.log("Updating preview to scene index:", node.currentSceneIndex);
                        
                        if (node.scenePaths.length > 0) {
                            node.updatePreview();
                        }
                    };
                    
                    console.log("✓ Hooked selected_scene_index widget callback");
                }
                
                // Create preview UI
                console.log("Creating preview UI...");
                this.createPreviewUI();
                
                console.log("=== onNodeCreated END ===");
                return result;
            };
            
            nodeType.prototype.createPreviewUI = function() {
                console.log("=== createPreviewUI START ===");
                
                // Title section with scene counter
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
                titleText.textContent = "🎬 Scene Preview";
                titleText.style.marginBottom = "5px";
                
                const sceneCounter = document.createElement("div");
                sceneCounter.id = "scene-counter";
                sceneCounter.style.cssText = `
                    font-size: 12px;
                    color: #888;
                    font-weight: normal;
                `;
                sceneCounter.textContent = "Use 'selected_scene_index' to navigate";
                
                titleDiv.appendChild(titleText);
                titleDiv.appendChild(sceneCounter);
                
                const titleWidget = this.addDOMWidget("preview_title", "div", titleDiv);
                titleWidget.computeSize = () => [0, 65];
                
                this.sceneCounterElement = sceneCounter;
                
                // Image container
                const imageContainer = document.createElement("div");
                imageContainer.style.cssText = `
                    background: #0a0a0a;
                    border-radius: 4px;
                    min-height: 200px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 20px;
                    margin: 10px 0;
                `;
                
                const imageElement = document.createElement("img");
                imageElement.id = "scene-preview-image";
                imageElement.style.cssText = `
                    max-width: 100%;
                    max-height: 400px;
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
                imagePlaceholder.textContent = "No image loaded";
                
                imageContainer.appendChild(imageElement);
                imageContainer.appendChild(imagePlaceholder);
                
                const imageWidget = this.addDOMWidget("preview_image", "div", imageContainer);
                imageWidget.computeSize = () => [0, 240];
                
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
                
                const labelWidget = this.addDOMWidget("desc_label", "div", descLabel);
                labelWidget.computeSize = () => [0, 25];
                
                // Description textarea
                const descTextarea = document.createElement("textarea");
                descTextarea.style.cssText = `
                    width: calc(100% - 20px);
                    min-height: 120px;
                    padding: 10px;
                    background: #2a2a2a;
                    color: #ddd;
                    border: 1px solid #444;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 11px;
                    resize: vertical;
                `;
                descTextarea.value = "No description available";
                descTextarea.addEventListener('input', () => {
                    console.log("Description changed");
                    const isModified = descTextarea.value !== this.originalDescription;
                    this.isDescriptionModified = isModified;
                    
                    if (this.saveDescBtn) {
                        this.saveDescBtn.disabled = !isModified;
                        this.saveDescBtn.style.opacity = isModified ? "1" : "0.5";
                    }
                    
                    if (this.sceneDescriptionWidget) {
                        this.sceneDescriptionWidget.value = descTextarea.value;
                    }
                });
                
                const descWidget = this.addDOMWidget("desc_textarea", "textarea", descTextarea);
                descWidget.computeSize = () => [0, 140];
                
                this.descriptionTextarea = descTextarea;
                
                // Buttons
                const buttonContainer = document.createElement("div");
                buttonContainer.style.cssText = `
                    display: flex;
                    gap: 10px;
                    margin-top: 10px;
                `;
                
                const saveDescBtn = document.createElement("button");
                saveDescBtn.textContent = "💾 Save Description";
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
                saveDescBtn.onclick = () => {
                    console.log("Save button clicked");
                    this.saveDescription();
                };
                
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
                clearDescBtn.onclick = () => {
                    console.log("Clear button clicked");
                    this.clearDescription();
                };
                
                buttonContainer.appendChild(saveDescBtn);
                buttonContainer.appendChild(clearDescBtn);
                
                const buttonWidget = this.addDOMWidget("desc_buttons", "div", buttonContainer);
                buttonWidget.computeSize = () => [0, 45];
                
                this.saveDescBtn = saveDescBtn;
                this.clearDescBtn = clearDescBtn;
                
                console.log("✓ Preview UI created successfully");
                console.log("=== createPreviewUI END ===");
            };
            
            nodeType.prototype.onExecuted = function(message) {
                console.log("=== onExecuted START ===");
                console.log("Full message:", JSON.stringify(message, null, 2));
                
                if (originalOnExecuted) {
                    originalOnExecuted.apply(this, arguments);
                }
                
                if (message?.scene_paths) {
                    console.log("scene_paths found:", message.scene_paths);
                    
                    const paths = Array.isArray(message.scene_paths[0]) 
                        ? message.scene_paths[0] 
                        : message.scene_paths;
                    
                    this.scenePaths = paths;
                    console.log("Scene paths set:", this.scenePaths);
                    
                    this.totalScenes = Array.isArray(message.total_scenes) 
                        ? message.total_scenes[0] 
                        : (message.total_scenes || paths.length);
                    
                    console.log(`Total scenes: ${this.totalScenes}`);
                    
                    // Update the max value of selected_scene_index widget
                    if (this.selectedSceneIndexWidget) {
                        this.selectedSceneIndexWidget.options.max = this.totalScenes;
                        console.log(`Updated selected_scene_index max to: ${this.totalScenes}`);
                    }
                    
                    let selectedIndex = 0;
                    if (message.selected_index) {
                        selectedIndex = Array.isArray(message.selected_index) 
                            ? message.selected_index[0] - 1
                            : message.selected_index - 1;
                    }
                    
                    this.currentSceneIndex = Math.max(0, Math.min(selectedIndex, this.scenePaths.length - 1));
                    console.log(`Current scene index: ${this.currentSceneIndex}`);
                    
                    if (this.scenePaths.length > 0) {
                        console.log("Calling updatePreview...");
                        this.updatePreview();
                    } else {
                        console.log("No scene paths to display");
                    }
                } else {
                    console.log("No scene_paths in message");
                }
                
                console.log("=== onExecuted END ===");
            };
            
            nodeType.prototype.updatePreview = async function() {
                console.log("=== updatePreview START ===");
                
                if (this.scenePaths.length === 0) {
                    console.log("No scenes to update");
                    return;
                }
                
                const scenePath = this.scenePaths[this.currentSceneIndex];
                console.log("Scene path:", scenePath);
                
                // Update scene counter
                if (this.sceneCounterElement) {
                    this.sceneCounterElement.textContent = `Viewing Scene ${this.currentSceneIndex + 1} of ${this.totalScenes}`;
                }
                
                const filename = scenePath.split('/').pop() || scenePath.split('\\').pop();
                console.log("Filename:", filename);
                
                let outputDir = "scene_outputs";
                const outputDirWidget = this.widgets?.find(w => w.name === "output_dir");
                if (outputDirWidget?.value) {
                    outputDir = outputDirWidget.value;
                }
                console.log("Output dir:", outputDir);
                
                // Load image
                console.log("Loading image...");
                try {
                    const imageUrl = `/video_scene/read_image?filename=${encodeURIComponent(filename)}&subfolder=${encodeURIComponent(outputDir)}&rand=${Math.random()}`;
                    console.log("Image URL:", imageUrl);
                    
                    const response = await fetch(imageUrl);
                    console.log("Image response status:", response.status);
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const objectUrl = URL.createObjectURL(blob);
                        
                        this.imageElement.src = objectUrl;
                        this.imageElement.style.display = "block";
                        this.imagePlaceholder.style.display = "none";
                        
                        console.log("✓ Image loaded successfully");
                        
                        setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
                    } else {
                        const errorText = await response.text();
                        console.error("Image load failed:", errorText);
                        throw new Error(errorText);
                    }
                } catch (error) {
                    console.error("Error loading image:", error);
                    this.imageElement.style.display = "none";
                    this.imagePlaceholder.style.display = "block";
                    this.imagePlaceholder.textContent = "Failed to load image";
                }
                
                // Load description
                console.log("Loading description...");
                try {
                    const txtFilename = filename.replace('.png', '.txt');
                    const descUrl = `/video_scene/read_description?filename=${encodeURIComponent(txtFilename)}&subfolder=${encodeURIComponent(outputDir)}&rand=${Math.random()}`;
                    console.log("Description URL:", descUrl);
                    
                    const response = await fetch(descUrl);
                    console.log("Description response status:", response.status);
                    
                    if (response.ok) {
                        const description = await response.text();
                        console.log("Description loaded, length:", description.length);
                        
                        if (this.descriptionTextarea) {
                            this.descriptionTextarea.value = description.trim() || "No description";
                            this.originalDescription = this.descriptionTextarea.value;
                            this.isDescriptionModified = false;
                            
                            if (this.saveDescBtn) {
                                this.saveDescBtn.disabled = true;
                                this.saveDescBtn.style.opacity = "0.5";
                            }
                            
                            if (this.sceneDescriptionWidget) {
                                this.sceneDescriptionWidget.value = description.trim();
                            }
                            
                            console.log("✓ Description loaded successfully");
                        }
                    } else {
                        const errorText = await response.text();
                        console.error("Description load failed:", errorText);
                        if (this.descriptionTextarea) {
                            this.descriptionTextarea.value = "No description available";
                            this.originalDescription = this.descriptionTextarea.value;
                        }
                    }
                } catch (error) {
                    console.error("Error loading description:", error);
                    if (this.descriptionTextarea) {
                        this.descriptionTextarea.value = "Failed to load description";
                        this.originalDescription = this.descriptionTextarea.value;
                    }
                }
                
                console.log("=== updatePreview END ===");
            };
            
            nodeType.prototype.saveDescription = async function() {
                console.log("=== saveDescription START ===");
                
                if (!this.descriptionTextarea || this.scenePaths.length === 0) {
                    alert("No description to save");
                    return;
                }
                
                const scenePath = this.scenePaths[this.currentSceneIndex];
                const filename = scenePath.split('/').pop() || scenePath.split('\\').pop();
                const txtFilename = filename.replace('.png', '.txt');
                
                let outputDir = "scene_outputs";
                const outputDirWidget = this.widgets?.find(w => w.name === "output_dir");
                if (outputDirWidget?.value) {
                    outputDir = outputDirWidget.value;
                }
                
                const content = this.descriptionTextarea.value;
                console.log("Saving:", txtFilename, "to:", outputDir);
                
                try {
                    const response = await api.fetchApi("/video_scene/save_description", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            filename: txtFilename,
                            subfolder: outputDir,
                            content: content
                        })
                    });
                    
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
                        console.error("Save failed:", errorText);
                    }
                } catch (error) {
                    console.error("Save error:", error);
                    alert("Error: " + error.message);
                }
                
                console.log("=== saveDescription END ===");
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
            
            console.log("✓ VideoSceneExtractor extension registered");
        }
    }
});

console.log("=== VideoSceneExtractor.js LOADED ===");