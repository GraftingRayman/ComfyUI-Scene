ComfyUI-Scene

This ComfyUI extension provides a complete workflow for analyzing video content, generating scene descriptions, and creating AI image prompts. It consists of three interconnected nodes that work together to transform video content into usable AI art prompts with visual previews.

<b>Updates:</b>

30/12/2023 - Complete rewrite, added sanitation and brought both nodes into one

27/12/2023 - Added Start and End Time selection

27/12/2023 - Initial Release

<b>To Do:</b>

Start and End Frame Selection

Add Moondream3 and other VLM's

# Video Scene Analysis & Prompt Generation
<b>Key Features:</b>

Video Scene Detection - Automatically detects scene changes in videos - OpenCV, PyScene VideoManager and PyScene OpenVideo can be chosen as the algo

AI-Powered Description Generation - Uses Moondream2 vision model to generate detailed scene descriptions

Visual Prompt Selection - Interactive UI to browse and select scenes with image previews

Prompt Customization - Modify image style and lighting parameters

Time-Range Support - Process specific sections of long videos

Real-time Preview - See keyframes and prompts without re-executing nodes

Edit and save the caption before generation


# Video Scene Viewer

Custom path selection

Visual Prompt Selection - Interactive UI to browse and select scenes with image previews

Prompt Customization - Modify image style and lighting parameters

Real-time Preview - See keyframes and prompts without re-executing nodes

Edit and save the caption before generation


# Installation:

Clone/copy this folder to ComfyUI/custom_nodes/

Ensure all Python dependencies are installed:


pip install torch torchvision transformers opencv-python Pillow scenedetect numpy aiohttp

Restart ComfyUI


<b>Model Requirements:</b>

Moondream2 (~1.5GB) will be automatically downloaded on first use

<b>Model location: </b>

~/.cache/huggingface/hub/models--vikhyatk--moondream2/


<b>Supported Video Formats:</b>

.mp4, .avi, .mov, .mkv, .webm, .flv, .wmv, .m4v, .mpg, .mpeg


<b>Notes:</b>

First run will download Moondream2 model (~1-5 minutes depending on internet)

Large videos may require significant disk space for keyframe extraction

Scene detection threshold can be adjusted for different video types

For long videos, process in time segments using start/end time parameters

<b>Video Scene Generator</b>

<img width="2572" height="1738" alt="image" src="https://github.com/user-attachments/assets/36cc9cb5-58fc-4136-bca4-153c26ff1b92" />

<b>Video Scene Generator</b>

<img width="2844" height="1783" alt="image" src="https://github.com/user-attachments/assets/1ef60f62-13be-46ba-a188-7dcda26f56e5" />

<b>Video Scene Viewer</b>

<img width="3204" height="1866" alt="image" src="https://github.com/user-attachments/assets/02de9356-74c7-484c-9217-f2c5d5fc5ea3" />



See workflow in workflow directory

Prompt can be modified before execution in Scene Prompt Selector

Scene Prompt Modifier can modify the prompt without regenerating all scenes.
