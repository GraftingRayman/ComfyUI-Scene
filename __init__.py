print("\033[95mComfyUI-Scene Video Scene Generation Nodes Loaded.\033[0m")

from .VideoSceneGeneration import VideoSceneGenerationNode
from .VideoSceneGenerationOpenVideo import VideoSceneGenerationOpenVideoNode
from .ScenePromptSelector import ScenePromptSelector
from .ScenePromptModifier import ScenePromptModifier

# Import server routes
from . import ScenePromptRoutes

NODE_CLASS_MAPPINGS = {
    "VideoSceneGenerationNode": VideoSceneGenerationNode,
    "VideoSceneGenerationOpenVideoNode": VideoSceneGenerationOpenVideoNode,
    "ScenePromptSelector": ScenePromptSelector,
    "ScenePromptModifier": ScenePromptModifier
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneGenerationNode": "Video Scene Analysis & Prompt Generation",
    "VideoSceneGenerationOpenVideoNode": "Video Scene Analysis & Prompt Generation - Open Video",
    "ScenePromptSelector": "Scene Prompt Selector",
    "ScenePromptModifier": "Scene Prompt Modifier"
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

WEB_DIRECTORY = "./web"