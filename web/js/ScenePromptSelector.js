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
                
                // Store the last valid path to remember it
                this.lastValidPath = null;
                this.isPathConnected = false;
                
                // Function to load scene prompt dynamically
                const loadScenePrompt = async () => {
                    const keyframesPathWidget = this.widgets?.find(w => w.name === "keyframes_path");
                    const sceneNumberWidget = this.widgets?.find(w => w.name === "scene_number");
                    
                    if (!keyframesPathWidget || !sceneNumberWidget || !this.promptPreview) {
                        console.log("Missing required widgets");
                        return;
                    }
                    
                    // Get the path - use widget value if available, otherwise use last valid path
                    let keyframesPath = keyframesPathWidget.value;
                    const sceneNumber = sceneNumberWidget.value;
                    
                    console.log("=== Loading scene ===");
                    console.log("Scene:", sceneNumber);
                    console.log("Path widget value:", keyframesPath);
                    console.log("Last valid path:", this.lastValidPath);
                    console.log("Is path connected:", this.isPathConnected);
                    
                    // If widget is empty but we have a last valid path, use it
                    if ((!keyframesPath || keyframesPath.trim() === "") && this.lastValidPath) {
                        console.log("Using last valid path:", this.lastValidPath);
                        keyframesPath = this.lastValidPath;
                    }
                    
                    // Check if input is connected but widget is empty
                    if ((!keyframesPath || keyframesPath.trim() === "") && this.isPathConnected) {
                        console.log("Path is connected but widget is empty - waiting for value");
                        this.promptPreview.value = "Path connected - waiting for value...";
                        if (this.imagePreview && this.imageStatus) {
                            this.imagePreview.style.display = "none";
                            this.imageStatus.style.display = "block";
                            this.imageStatus.textContent = "Execute connected node first";
                        }
                        return;
                    }
                    
                    if (!keyframesPath || keyframesPath.trim() === "") {
                        this.promptPreview.value = "Please provide keyframes path";
                        if (this.imagePreview && this.imageStatus) {
                            this.imagePreview.style.display = "none";
                            this.imageStatus.style.display = "block";
                            this.imageStatus.textContent = "No path provided";
                        }
                        return;
                    }
                    
                    // Store this as last valid path
                    this.lastValidPath = keyframesPath;
                    
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
                            if (data.has_image && data.image_file && this.imagePreview && this.imageStatus) {
                                // Try multiple possible paths
                                const possiblePaths = [
                                    { path: `${keyframesPath}/keyframes/${data.image_file}`, desc: "keyframes subdirectory" },
                                    { path: `${keyframesPath}/${data.image_file}`, desc: "direct path" },
                                ];
                                
                                const tryLoadImage = async (index) => {
                                    if (index >= possiblePaths.length) {
                                        this.imagePreview.style.display = "none";
                                        this.imageStatus.style.display = "block";
                                        this.imageStatus.textContent = "Image not found";
                                        return;
                                    }
                                    
                                    const pathInfo = possiblePaths[index];
                                    const imageUrl = `/scene_prompt/image?path=${encodeURIComponent(pathInfo.path)}`;
                                    
                                    console.log(`Trying to load image from: ${pathInfo.desc}`);
                                    
                                    this.imagePreview.onload = () => {
                                        console.log(`✓ Image loaded successfully from: ${pathInfo.desc}`);
                                        this.imagePreview.style.display = "block";
                                        this.imageStatus.style.display = "none";
                                    };
                                    
                                    this.imagePreview.onerror = () => {
                                        console.log(`✗ Failed to load from: ${pathInfo.desc}`);
                                        tryLoadImage(index + 1);
                                    };
                                    
                                    this.imagePreview.src = imageUrl;
                                };
                                
                                tryLoadImage(0);
                            } else if (this.imagePreview && this.imageStatus) {
                                this.imagePreview.style.display = "none";
                                this.imageStatus.style.display = "block";
                                this.imageStatus.textContent = data.has_image ? "No image file specified" : "No image available";
                            }
                        } else {
                            const errorText = await response.text();
                            console.error("API error:", errorText);
                            this.promptPreview.value = `Error loading prompt: ${response.status} ${response.statusText}`;
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
                    
                    // Also listen for input events for real-time updates
                    if (sceneNumberWidget.inputEl) {
                        sceneNumberWidget.inputEl.addEventListener('input', () => {
                            setTimeout(() => loadScenePrompt(), 100);
                        });
                    }
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
                    
                    // Also listen for input events
                    if (keyframesPathWidget.inputEl) {
                        keyframesPathWidget.inputEl.addEventListener('input', () => {
                            setTimeout(() => loadScenePrompt(), 300);
                        });
                    }
                    
                    // Check if the widget gets updated from a connection
                    const originalOnResize = keyframesPathWidget.onResize;
                    keyframesPathWidget.onResize = function() {
                        if (originalOnResize) {
                            originalOnResize.apply(this, arguments);
                        }
                        // When widget resizes (which happens when value updates), try to load
                        setTimeout(() => {
                            if (keyframesPathWidget.value && keyframesPathWidget.value.trim() !== "") {
                                console.log("Keyframes path widget updated to:", keyframesPathWidget.value);
                                // Store this as the last valid path
                                this.lastValidPath = keyframesPathWidget.value;
                                loadScenePrompt();
                            }
                        }, 100);
                    };
                    
                    // Add a MutationObserver to detect when the input value changes
                    if (keyframesPathWidget.inputEl) {
                        const observer = new MutationObserver((mutations) => {
                            mutations.forEach((mutation) => {
                                if (mutation.type === 'attributes' && mutation.attributeName === 'value') {
                                    const newValue = keyframesPathWidget.inputEl.value;
                                    console.log("MutationObserver detected value change:", newValue);
                                    if (newValue && newValue.trim() !== "") {
                                        this.lastValidPath = newValue;
                                        setTimeout(() => loadScenePrompt(), 100);
                                    }
                                }
                            });
                        });
                        
                        observer.observe(keyframesPathWidget.inputEl, {
                            attributes: true,
                            attributeFilter: ['value']
                        });
                    }
                }
                
                // Check if keyframes_path input is connected
                const checkConnectionStatus = () => {
                    const keyframesPathInput = this.inputs?.find(i => i.name === "keyframes_path");
                    this.isPathConnected = keyframesPathInput && keyframesPathInput.link != null;
                    console.log("Connection status check - isPathConnected:", this.isPathConnected);
                    
                    // If connected, show appropriate message
                    if (this.isPathConnected && (!this.lastValidPath || this.lastValidPath.trim() === "")) {
                        console.log("Path is connected but no value yet");
                        if (this.promptPreview) {
                            this.promptPreview.value = "Path connected - execute upstream node first";
                        }
                    }
                };
                
                // Handle execution updates to display the selected prompt
                const originalOnExecuted = nodeType.prototype.onExecuted;
                nodeType.prototype.onExecuted = function(message) {
                    originalOnExecuted?.apply(this, arguments);
                    
                    console.log("ScenePromptSelector onExecuted, message:", message);
                    
                    // Check connection status
                    checkConnectionStatus();
                    
                    // Update preview with the selected prompt from execution
                    if (message && this.promptPreview) {
                        let promptText = null;
                        
                        // Try different ways to get the text
                        if (message.text) {
                            promptText = Array.isArray(message.text) ? message.text[0] : message.text;
                        } else if (message.selected_prompt) {
                            promptText = Array.isArray(message.selected_prompt) ? message.selected_prompt[0] : message.selected_prompt;
                        } else if (message.result && message.result[0]) {
                            // Try to get from result tuple
                            promptText = message.result[0];
                        }
                        
                        console.log("Extracted promptText:", promptText ? promptText.substring(0, 100) + "..." : "null");
                        
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
                    
                    // After execution, check if we have a path in the widget and try to load
                    setTimeout(() => {
                        const keyframesPathWidget = this.widgets?.find(w => w.name === "keyframes_path");
                        if (keyframesPathWidget && keyframesPathWidget.value && keyframesPathWidget.value.trim() !== "") {
                            console.log("After execution, storing and loading with path:", keyframesPathWidget.value);
                            this.lastValidPath = keyframesPathWidget.value;
                            loadScenePrompt();
                        }
                    }, 200);
                };
                
                // Initial setup
                setTimeout(() => {
                    // Check connection status
                    checkConnectionStatus();
                    
                    // Initial load if we have values
                    const keyframesPathWidget = this.widgets?.find(w => w.name === "keyframes_path");
                    if (keyframesPathWidget && keyframesPathWidget.value) {
                        console.log("Initial load with path:", keyframesPathWidget.value);
                        this.lastValidPath = keyframesPathWidget.value;
                        loadScenePrompt();
                    }
                }, 300);
                
                return r;
            };
        }
    }
});