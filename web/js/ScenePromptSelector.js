import { app } from "/scripts/app.js";
import { ComfyWidgets } from "/scripts/widgets.js";
import { api } from "/scripts/api.js";

app.registerExtension({
    name: "ScenePromptSelectorExtension",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "ScenePromptSelector") {
            console.log("=== Registering ScenePromptSelector extension ===");

            const originalNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function() {
                const r = originalNodeCreated ? originalNodeCreated.apply(this, arguments) : undefined;
                
                // Find the selected_prompt output widget (the one we want to hide and replace)
                let promptWidget = this.widgets?.find(w => w.name === "selected_prompt");
                
                // If no selected_prompt widget exists, create a hidden one
                if (!promptWidget) {
                    promptWidget = this.addWidget("text", "selected_prompt", "", () => {}, {
                        serialize: true
                    });
                }
                
                if (promptWidget) {
                    // Hide the widget
                    promptWidget.computeSize = () => [0, -4];
                    if (promptWidget.inputEl) {
                        promptWidget.inputEl.style.display = "none";
                    }
                }
                
                // Create a preview widget for displaying/editing the prompt
                const previewWidget = ComfyWidgets["STRING"](
                    this, 
                    "prompt_preview", 
                    ["STRING", { multiline: true }], 
                    app
                )?.widget;
                
                if (previewWidget) {
                    previewWidget.inputEl.readOnly = false;
                    previewWidget.inputEl.style.opacity = 1.0;
                    previewWidget.inputEl.style.fontFamily = "monospace";
                    previewWidget.inputEl.style.fontSize = "11px";
                    previewWidget.inputEl.rows = 10;
                    previewWidget.value = "Select a scene number to view prompt...";
                    
                    this.promptPreview = previewWidget;
                    
                    // Sync preview changes back to the hidden widget
                    previewWidget.inputEl.addEventListener('input', () => {
                        if (promptWidget) {
                            promptWidget.value = previewWidget.value;
                        }
                        this.setDirtyCanvas(true, true);
                    });
                }
                
                // Create image preview widget
                const imageContainer = document.createElement("div");
                imageContainer.style.width = "100%";
                imageContainer.style.marginTop = "10px";
                imageContainer.style.marginBottom = "10px";
                imageContainer.style.textAlign = "center";
                imageContainer.style.backgroundColor = "#1a1a1a";
                imageContainer.style.borderRadius = "4px";
                imageContainer.style.padding = "10px";
                imageContainer.style.boxSizing = "border-box";
                
                const imagePreview = document.createElement("img");
                imagePreview.style.maxWidth = "100%";
                imagePreview.style.height = "auto";
                imagePreview.style.display = "none";
                imagePreview.style.borderRadius = "4px";
                
                const imageStatus = document.createElement("div");
                imageStatus.textContent = "No image loaded";
                imageStatus.style.color = "#888";
                imageStatus.style.padding = "20px";
                imageStatus.style.fontSize = "12px";
                
                imageContainer.appendChild(imagePreview);
                imageContainer.appendChild(imageStatus);
                
                const imageWidget = this.addDOMWidget("image_preview", "div", imageContainer, {
                    getValue: () => null,
                    setValue: () => {},
                });
                imageWidget.computeSize = () => [0, 200];
                
                this.imagePreview = imagePreview;
                this.imageStatus = imageStatus;
                
                // Function to load scene prompt dynamically
                const loadScenePrompt = async () => {
                    const keyframesPathWidget = this.widgets?.find(w => w.name === "keyframes_path");
                    const sceneNumberWidget = this.widgets?.find(w => w.name === "scene_number");
                    
                    if (!keyframesPathWidget || !sceneNumberWidget || !this.promptPreview) {
                        console.log("Missing required widgets");
                        return;
                    }
                    
                    const keyframesPath = keyframesPathWidget.value;
                    const sceneNumber = sceneNumberWidget.value;
                    
                    if (!keyframesPath || keyframesPath.trim() === "") {
                        this.promptPreview.value = "Please provide keyframes path";
                        if (this.imagePreview && this.imageStatus) {
                            this.imagePreview.style.display = "none";
                            this.imageStatus.style.display = "block";
                            this.imageStatus.textContent = "No path provided";
                        }
                        return;
                    }
                    
                    console.log("Loading scene:", sceneNumber, "from:", keyframesPath);
                    
                    // Check if prompts_text is connected
                    const promptsTextInput = this.inputs?.find(i => i.name === "prompts_text");
                    const isPromptsConnected = promptsTextInput && promptsTextInput.link != null;
                    
                    if (isPromptsConnected) {
                        // If prompts_text is connected, we need to execute to get the data
                        this.promptPreview.value = "Prompts connected - execute node to view";
                        if (this.imagePreview && this.imageStatus) {
                            this.imagePreview.style.display = "none";
                            this.imageStatus.style.display = "block";
                            this.imageStatus.textContent = "Execute node to view image";
                        }
                        console.log("Prompts text is connected, skipping dynamic load");
                        return;
                    }
                    
                    // Show loading state
                    this.promptPreview.value = "Loading...";
                    if (this.imagePreview && this.imageStatus) {
                        this.imagePreview.style.display = "none";
                        this.imageStatus.style.display = "block";
                        this.imageStatus.textContent = "Loading image...";
                    }
                    
                    try {
                        const response = await api.fetchApi(
                            `/scene_prompt/read?keyframes_path=${encodeURIComponent(keyframesPath)}&scene_number=${sceneNumber}`
                        );
                        
                        if (response.ok) {
                            const data = await response.json();
                            console.log("Loaded scene data:", data);
                            
                            if (data.prompt) {
                                this.promptPreview.value = data.prompt;
                                
                                // Sync to hidden widget
                                if (promptWidget) {
                                    promptWidget.value = data.prompt;
                                }
                                
                                // Auto-adjust rows based on content
                                const lines = data.prompt.split('\n').length;
                                this.promptPreview.inputEl.rows = Math.min(Math.max(lines, 5), 20);
                                
                                // Update total_scenes if we have that widget
                                const totalScenesWidget = this.widgets?.find(w => w.name === "total_scenes");
                                if (totalScenesWidget && data.total_scenes) {
                                    totalScenesWidget.value = data.total_scenes;
                                }
                            } else if (data.error) {
                                this.promptPreview.value = `Error: ${data.error}`;
                            }
                            
                            // Load and display image
                            if (data.has_image && this.imagePreview && this.imageStatus) {
                                // Build image URL
                                const sceneFile = `scene_${String(sceneNumber).padStart(3, '0')}.png`;
                                
                                // Check if keyframes subdirectory exists by trying both paths
                                let imagePath = `${keyframesPath}/keyframes/${sceneFile}`;
                                
                                // Convert to URL-friendly format and load image
                                const imageUrl = `/scene_prompt/image?path=${encodeURIComponent(imagePath)}`;
                                
                                this.imagePreview.onload = () => {
                                    this.imagePreview.style.display = "block";
                                    this.imageStatus.style.display = "none";
                                };
                                
                                this.imagePreview.onerror = () => {
                                    // Try without keyframes subdirectory
                                    const altImagePath = `${keyframesPath}/${sceneFile}`;
                                    const altImageUrl = `/scene_prompt/image?path=${encodeURIComponent(altImagePath)}`;
                                    this.imagePreview.src = altImageUrl;
                                    
                                    this.imagePreview.onerror = () => {
                                        this.imagePreview.style.display = "none";
                                        this.imageStatus.style.display = "block";
                                        this.imageStatus.textContent = "Image not found";
                                    };
                                };
                                
                                this.imagePreview.src = imageUrl;
                            } else if (this.imagePreview && this.imageStatus) {
                                this.imagePreview.style.display = "none";
                                this.imageStatus.style.display = "block";
                                this.imageStatus.textContent = "No image available";
                            }
                        } else {
                            const errorText = await response.text();
                            this.promptPreview.value = `Error loading prompt: ${errorText}`;
                            if (this.imagePreview && this.imageStatus) {
                                this.imagePreview.style.display = "none";
                                this.imageStatus.style.display = "block";
                                this.imageStatus.textContent = "Error loading image";
                            }
                        }
                    } catch (error) {
                        console.error("Error loading scene prompt:", error);
                        this.promptPreview.value = `Error: ${error.message}`;
                        if (this.imagePreview && this.imageStatus) {
                            this.imagePreview.style.display = "none";
                            this.imageStatus.style.display = "block";
                            this.imageStatus.textContent = `Error: ${error.message}`;
                        }
                    }
                };
                
                // Hook into scene_number widget to trigger dynamic updates
                const sceneNumberWidget = this.widgets?.find(w => w.name === "scene_number");
                if (sceneNumberWidget) {
                    const originalCallback = sceneNumberWidget.callback;
                    
                    sceneNumberWidget.callback = function(value) {
                        if (originalCallback) {
                            originalCallback.call(sceneNumberWidget, value);
                        }
                        
                        console.log("Scene number changed to:", value);
                        loadScenePrompt();
                    };
                }
                
                // Hook into keyframes_path widget to trigger updates
                const keyframesPathWidget = this.widgets?.find(w => w.name === "keyframes_path");
                if (keyframesPathWidget) {
                    const originalCallback = keyframesPathWidget.callback;
                    
                    keyframesPathWidget.callback = function(value) {
                        if (originalCallback) {
                            originalCallback.call(keyframesPathWidget, value);
                        }
                        
                        console.log("Keyframes path changed to:", value);
                        loadScenePrompt();
                    };
                }
                
                // Initial load if we have values
                setTimeout(() => {
                    if (keyframesPathWidget && keyframesPathWidget.value) {
                        loadScenePrompt();
                    }
                }, 100);
                
                return r;
            };
            
            // Handle execution updates to display the selected prompt (for when prompts_text is connected)
            const originalOnExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                originalOnExecuted?.apply(this, arguments);
                
                console.log("ScenePromptSelector onExecuted, message:", message);
                
                // Update preview with the selected prompt from execution
                if (message && this.promptPreview) {
                    let promptText = null;
                    
                    // Try different ways to get the text
                    if (message.text) {
                        promptText = Array.isArray(message.text) ? message.text[0] : message.text;
                    } else if (message.selected_prompt) {
                        promptText = Array.isArray(message.selected_prompt) ? message.selected_prompt[0] : message.selected_prompt;
                    }
                    
                    console.log("Extracted promptText:", promptText);
                    
                    if (promptText && typeof promptText === 'string') {
                        this.promptPreview.value = promptText;
                        
                        // Sync to hidden widget
                        const promptWidget = this.widgets?.find(w => w.name === "selected_prompt");
                        if (promptWidget) {
                            promptWidget.value = promptText;
                        }
                        
                        // Auto-adjust rows based on content
                        const lines = promptText.split('\n').length;
                        this.promptPreview.inputEl.rows = Math.min(Math.max(lines, 5), 20);
                        
                        console.log("Updated preview with prompt, lines:", lines);
                    } else {
                        console.warn("No valid prompt text found in message");
                    }
                }
            };
        }
    }
});