print("\033[95mComfyUI-VideoScene Extractor Nodes Loaded.\033[0m")

# Import the main node class
from .VideoSceneExtractor import VideoSceneGenerationNode
from .VideoScenePromptModifier import VideoScenePromptModifier
from .VideoSceneViewer import VideoSceneViewer

NODE_CLASS_MAPPINGS = {
    "VideoSceneGenerationNode": VideoSceneGenerationNode,
    "VideoScenePromptModifier": VideoScenePromptModifier,
    "VideoSceneViewer": VideoSceneViewer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneGenerationNode": "Video Scene Analysis & Prompt Generation",
    "VideoScenePromptModifier": "Video Scene Analysis Prompt Modifier",
    "VideoSceneViewer": "Video Scene Viewer",


}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]


WEB_DIRECTORY = "./web"

# Import routes to register API endpoints
try:
    from . import routes
    print("\033[92m✓ VideoSceneExtractor API routes registered\033[0m")
except Exception as e:
    print(f"\033[91m✗ Failed to load VideoSceneExtractor routes: {e}\033[0m")