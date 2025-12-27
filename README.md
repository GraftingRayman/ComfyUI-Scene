ComfyUI-Scene

This ComfyUI extension provides a complete workflow for analyzing video content, generating scene descriptions, and creating AI image prompts. It consists of three interconnected nodes that work together to transform video content into usable AI art prompts with visual previews.

Key Features:
Video Scene Detection - Automatically detects scene changes in videos

AI-Powered Description Generation - Uses Moondream2 vision model to generate detailed scene descriptions

Visual Prompt Selection - Interactive UI to browse and select scenes with image previews

Prompt Customization - Modify image style and lighting parameters

Time-Range Support - Process specific sections of long videos

Real-time Preview - See keyframes and prompts without re-executing nodes



Installation:
Clone/copy this folder to ComfyUI/custom_nodes/

Ensure all Python dependencies are installed:

bash
pip install torch torchvision transformers opencv-python Pillow scenedetect numpy aiohttp
Restart ComfyUI

Model Requirements:
Moondream2 (~1.5GB) will be automatically downloaded on first use

Model location: ~/.cache/huggingface/hub/models--vikhyatk--moondream2/


Supported Video Formats:
.mp4, .avi, .mov, .mkv, .webm, .flv, .wmv, .m4v, .mpg, .mpeg


Notes:
First run will download Moondream2 model (~1-5 minutes depending on internet)

Large videos may require significant disk space for keyframe extraction

Scene detection threshold can be adjusted for different video types

For long videos, process in time segments using start/end time parameters


<img width="3288" height="1729" alt="image" src="https://github.com/user-attachments/assets/935757b8-10e6-44ca-8a36-fad956074ab1" />


<img width="3352" height="1745" alt="image" src="https://github.com/user-attachments/assets/04328bf0-2cec-42f8-8eb5-4c43c982dc22" />


See workflow in workflow directory

Prompt can be modified before execution in Scene Prompt Selector

Scene Prompt Modifier can modify the prompt without regenerating all scenes.
