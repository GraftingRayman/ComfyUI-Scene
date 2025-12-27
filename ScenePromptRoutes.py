import os
import re
import server
from aiohttp import web

@server.PromptServer.instance.routes.get("/scene_prompt/read")
async def read_scene_prompt(request):
    """
    API endpoint to read scene prompt and check for image existence
    """
    keyframes_path = request.query.get("keyframes_path", "")
    scene_number = request.query.get("scene_number", "1")
    
    print(f"=== Scene Prompt Read Request ===")
    print(f"Keyframes path: {keyframes_path}")
    print(f"Scene number: {scene_number}")
    
    if not keyframes_path:
        return web.json_response({
            "error": "No keyframes path provided",
            "prompt": "",
            "has_image": False
        }, status=400)
    
    try:
        scene_number = int(scene_number)
    except:
        return web.json_response({
            "error": "Invalid scene number",
            "prompt": "",
            "has_image": False
        }, status=400)
    
    # Check if path exists
    print(f"Checking if path exists: {keyframes_path}")
    print(f"Path exists: {os.path.exists(keyframes_path)}")
    print(f"Is directory: {os.path.isdir(keyframes_path)}")
    
    if not os.path.exists(keyframes_path):
        return web.json_response({
            "error": f"Keyframes path does not exist: {keyframes_path}",
            "prompt": "",
            "has_image": False
        }, status=404)
    
    # Check if keyframes subdirectory exists
    keyframes_subdir = os.path.join(keyframes_path, "keyframes")
    if os.path.exists(keyframes_subdir):
        actual_path = keyframes_subdir
        print(f"Using keyframes subdirectory: {actual_path}")
    else:
        actual_path = keyframes_path
        print(f"Using direct path: {actual_path}")
    
    # List all files in directory
    if os.path.isdir(actual_path):
        try:
            files = os.listdir(actual_path)
            print(f"Files in directory: {files}")
        except Exception as e:
            print(f"Error listing directory: {e}")
    
    # Find matching files for this scene
    scene_idx = scene_number - 1
    
    # Pattern for new format: scene_001_01m23s456ms.png
    png_pattern = f"scene_{scene_number:03d}_"
    
    # Find matching PNG files
    png_files = []
    txt_files = []
    
    if os.path.isdir(actual_path):
        try:
            for filename in os.listdir(actual_path):
                if filename.startswith(png_pattern) and filename.endswith('.png'):
                    png_files.append(filename)
                elif filename.startswith(png_pattern) and filename.endswith('.txt'):
                    txt_files.append(filename)
        except Exception as e:
            print(f"Error listing files: {e}")
    
    # If no files found with timestamp pattern, try old format
    if not png_files:
        old_png = f"scene_{scene_number:03d}.png"
        old_txt = f"scene_{scene_number:03d}.txt"
        if os.path.exists(os.path.join(actual_path, old_png)):
            png_files = [old_png]
        if os.path.exists(os.path.join(actual_path, old_txt)):
            txt_files = [old_txt]
    
    print(f"Found PNG files: {png_files}")
    print(f"Found TXT files: {txt_files}")
    
    # Security check: ensure paths are within allowed directory
    abs_base_path = os.path.abspath(keyframes_path)
    
    # Read prompt
    prompt_text = ""
    
    # Try to find and read prompt file
    for txt_file in txt_files:
        prompt_path = os.path.join(actual_path, txt_file)
        abs_prompt_path = os.path.abspath(prompt_path)
        
        if not abs_prompt_path.startswith(abs_base_path):
            continue
            
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_text = f.read().strip()
            print(f"Loaded prompt from: {prompt_path}")
            break
        except Exception as e:
            print(f"Error reading prompt file {prompt_path}: {e}")
    
    # If no prompt file found, fallback
    if not prompt_text:
        # Check if prompts_text.txt exists
        prompts_text_path = os.path.join(actual_path, "scene_prompts.txt")
        if os.path.exists(prompts_text_path):
            try:
                with open(prompts_text_path, 'r', encoding='utf-8') as f:
                    all_prompts = f.read()
                    # Parse prompts
                    scenes = all_prompts.strip().split('\n\n')
                    if scene_idx < len(scenes):
                        scene_text = scenes[scene_idx].strip()
                        # Try to extract prompt after "Scene X:"
                        match = re.match(r'Scene\s+\d+:\s*(.+)', scene_text, re.DOTALL)
                        if match:
                            prompt_text = match.group(1).strip()
                        else:
                            prompt_text = scene_text
                    else:
                        prompt_text = f"Scene {scene_number}"
            except Exception as e:
                print(f"Error reading scene_prompts.txt: {e}")
                prompt_text = f"Scene {scene_number}"
        else:
            prompt_text = f"Scene {scene_number}"
    
    # Check if image exists
    has_image = False
    image_file = None
    
    for png_file in png_files:
        image_path = os.path.join(actual_path, png_file)
        if os.path.exists(image_path):
            has_image = True
            image_file = png_file
            break
    
    # Count total scenes (based on unique scene numbers in filenames)
    total_scenes = 0
    scene_numbers = set()
    
    if os.path.isdir(actual_path):
        try:
            for filename in os.listdir(actual_path):
                if filename.startswith("scene_") and (filename.endswith(".png") or filename.endswith(".txt")):
                    # Extract scene number
                    # Match patterns: scene_001_ or scene_001.
                    match = re.match(r'scene_(\d{3})[_\.]', filename)
                    if match:
                        scene_num = int(match.group(1))
                        scene_numbers.add(scene_num)
        except Exception as e:
            print(f"Error counting scenes: {e}")
    
    total_scenes = len(scene_numbers) if scene_numbers else 0
    
    # If no scenes found by parsing, count PNG files
    if total_scenes == 0:
        png_count = sum(1 for f in os.listdir(actual_path) 
                       if f.startswith("scene_") and f.endswith(".png"))
        total_scenes = png_count
    
    return web.json_response({
        "prompt": prompt_text,
        "has_image": has_image,
        "total_scenes": total_scenes,
        "scene_number": scene_number,
        "image_file": image_file
    }, status=200)


@server.PromptServer.instance.routes.get("/scene_prompt/image")
async def serve_scene_image(request):
    """
    API endpoint to serve scene images
    """
    image_path = request.query.get("path", "")
    
    print(f"=== Scene Image Request ===")
    print(f"Image path: {image_path}")
    
    if not image_path:
        return web.Response(text="No image path provided", status=400)
    
    # Security check: prevent directory traversal
    if ".." in image_path or image_path.startswith("/"):
        return web.Response(text="Invalid image path", status=403)
    
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return web.Response(text="Image not found", status=404)
    
    if not image_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        return web.Response(text="Invalid image format", status=400)
    
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Determine content type
        if image_path.lower().endswith('.png'):
            content_type = 'image/png'
        else:
            content_type = 'image/jpeg'
        
        return web.Response(body=image_data, content_type=content_type, status=200)
    except Exception as e:
        print(f"Error serving image: {e}")
        return web.Response(text=f"Error serving image: {str(e)}", status=500)