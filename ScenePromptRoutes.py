# Add these routes to your existing routes.py file
import os
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
    
    # Build file paths
    scene_idx = scene_number - 1
    prompt_file = f"scene_{scene_number:03d}.txt"
    image_file = f"scene_{scene_number:03d}.png"
    
    prompt_path = os.path.join(actual_path, prompt_file)
    image_path = os.path.join(actual_path, image_file)
    
    print(f"Looking for prompt file: {prompt_path}")
    print(f"Prompt file exists: {os.path.exists(prompt_path)}")
    print(f"Looking for image file: {image_path}")
    print(f"Image file exists: {os.path.exists(image_path)}")
    
    # Security check: ensure paths are within allowed directory
    abs_prompt_path = os.path.abspath(prompt_path)
    abs_base_path = os.path.abspath(keyframes_path)
    print(f"Absolute prompt path: {abs_prompt_path}")
    print(f"Absolute base path: {abs_base_path}")
    print(f"Security check: {abs_prompt_path.startswith(abs_base_path)}")
    
    if not abs_prompt_path.startswith(abs_base_path):
        return web.json_response({
            "error": "Invalid file path",
            "prompt": "",
            "has_image": False
        }, status=403)
    
    # Read prompt if exists
    prompt_text = ""
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_text = f.read().strip()
        except Exception as e:
            print(f"Error reading prompt file: {e}")
            prompt_text = f"Scene {scene_number}"
    else:
        # Check if prompts_text exists in the directory
        prompts_text_path = os.path.join(actual_path, "prompts_text.txt")
        if os.path.exists(prompts_text_path):
            try:
                with open(prompts_text_path, 'r', encoding='utf-8') as f:
                    all_prompts = f.read()
                    # Parse prompts
                    scenes = all_prompts.strip().split('\n\n')
                    if scene_idx < len(scenes):
                        scene_text = scenes[scene_idx].strip()
                        # Try to extract prompt after "Scene X:"
                        import re
                        match = re.match(r'Scene\s+\d+:\s*(.+)', scene_text, re.DOTALL)
                        if match:
                            prompt_text = match.group(1).strip()
                        else:
                            prompt_text = scene_text
                    else:
                        prompt_text = f"Scene {scene_number}"
            except Exception as e:
                print(f"Error reading prompts_text.txt: {e}")
                prompt_text = f"Scene {scene_number}"
        else:
            prompt_text = f"Scene {scene_number}"
    
    # Check if image exists
    has_image = os.path.exists(image_path)
    
    # Count total scenes
    total_scenes = 0
    if os.path.exists(actual_path):
        for filename in os.listdir(actual_path):
            if filename.startswith("scene_") and filename.endswith(".png"):
                total_scenes += 1
    
    return web.json_response({
        "prompt": prompt_text,
        "has_image": has_image,
        "total_scenes": total_scenes,
        "scene_number": scene_number
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