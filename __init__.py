print("\033[95mComfyUI-Scene Video Scene Extractor - Loading Nodes...\033[0m")

# Import and load each node individually with status messages
try:
    from .VideoSceneExtractor import VideoSceneGenerationNode
    print("\033[92m✓ Loaded: VideoSceneGenerationNode\033[0m")
except Exception as e:
    print(f"\033[91m✗ Failed to load VideoSceneGenerationNode: {e}\033[0m")
    VideoSceneGenerationNode = None

try:
    from .VideoScenePromptModifier import VideoScenePromptModifier
    print("\033[92m✓ Loaded: VideoScenePromptModifier\033[0m")
except Exception as e:
    print(f"\033[91m✗ Failed to load VideoScenePromptModifier: {e}\033[0m")
    VideoScenePromptModifier = None

try:
    from .VideoSceneViewer import VideoSceneViewer
    print("\033[92m✓ Loaded: VideoSceneViewer\033[0m")
except Exception as e:
    print(f"\033[91m✗ Failed to load VideoSceneViewer: {e}\033[0m")
    VideoSceneViewer = None

try:
    from .VideoSceneIncrementer import VideoSceneIncrementer
    print("\033[92m✓ Loaded: VideoSceneIncrementer\033[0m")
except Exception as e:
    print(f"\033[91m✗ Failed to load VideoSceneIncrementer: {e}\033[0m")
    VideoSceneIncrementer = None

try:
    from .VideoSceneCaption import VideoSceneCaption
    print("\033[92m✓ Loaded: VideoSceneCaption\033[0m")
except Exception as e:
    print(f"\033[91m✗ Failed to load VideoSceneCaption: {e}\033[0m")
    VideoSceneCaption = None

# Build NODE_CLASS_MAPPINGS only with successfully loaded nodes
NODE_CLASS_MAPPINGS = {}
if VideoSceneGenerationNode:
    NODE_CLASS_MAPPINGS["VideoSceneGenerationNode"] = VideoSceneGenerationNode
if VideoScenePromptModifier:
    NODE_CLASS_MAPPINGS["VideoScenePromptModifier"] = VideoScenePromptModifier
if VideoSceneViewer:
    NODE_CLASS_MAPPINGS["VideoSceneViewer"] = VideoSceneViewer
if VideoSceneIncrementer:
    NODE_CLASS_MAPPINGS["VideoSceneIncrementer"] = VideoSceneIncrementer
if VideoSceneCaption:
    NODE_CLASS_MAPPINGS["VideoSceneCaption"] = VideoSceneCaption

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneGenerationNode": "Video Scene Analysis & Prompt Generation",
    "VideoScenePromptModifier": "Video Scene Analysis Prompt Modifier",
    "VideoSceneViewer": "Video Scene Viewer",
    "VideoSceneIncrementer": "Video Scene Incrementer",
    "VideoSceneCaption": "Video Scene Caption",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
WEB_DIRECTORY = "./web"

# Import routes to register API endpoints
try:
    from . import routes
    print("\033[92m✓ ComfyUI-Scene Video Scene Extractor API routes registered\033[0m")
except Exception as e:
    print(f"\033[91m✗ Failed to load ComfyUI-Scene Video Scene Extractor routes: {e}\033[0m")

print("\033[95mComfyUI-Scene Video Scene Extractor - All nodes loaded successfully!\033[0m")