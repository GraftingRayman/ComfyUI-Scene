print("\033[95mLoading Video Scene Generation Nodes...\033[0m")

from .VideoSceneGeneration import VideoSceneGenerationNode
from .ScenePromptSelector import ScenePromptSelector
from .ScenePromptModifier import ScenePromptModifier

# Import server routes
from . import ScenePromptRoutes

NODE_CLASS_MAPPINGS = {
    "VideoSceneGenerationNode": VideoSceneGenerationNode,
    "ScenePromptSelector": ScenePromptSelector,
    "ScenePromptModifier": ScenePromptModifier
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneGenerationNode": "Video Scene Analysis & Prompt Generation",
    "ScenePromptSelector": "Scene Prompt Selector",
    "ScenePromptModifier": "Scene Prompt Modifier"
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

WEB_DIRECTORY = "./web"