import os
import json
import server
from aiohttp import web
import folder_paths

@server.PromptServer.instance.routes.get("/video_scene/read_image")
async def read_scene_image(request):
    """
    API endpoint to read scene image files from ComfyUI output directory
    """
    filename = request.query.get("filename", "")
    subfolder = request.query.get("subfolder", "scene_outputs")
    
    if not filename:
        return web.Response(text="No filename provided", status=400)
    
    # Get ComfyUI output directory
    output_dir = folder_paths.get_output_directory()
    
    # Build file path
    file_path = os.path.join(output_dir, subfolder, filename)
    
    # Security check: ensure the file is within the output directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        return web.Response(text="Invalid file path", status=403)
    
    if not os.path.exists(file_path):
        return web.Response(text="Image not found", status=404)
    
    # Check if it's an image file
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
        return web.Response(text="Not an image file", status=400)
    
    try:
        with open(file_path, 'rb') as f:
            image_data = f.read()
        
        # Determine content type based on file extension
        if filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        elif filename.lower().endswith('.bmp'):
            content_type = 'image/bmp'
        elif filename.lower().endswith('.webp'):
            content_type = 'image/webp'
        else:
            content_type = 'application/octet-stream'
        
        return web.Response(body=image_data, content_type=content_type)
    except Exception as e:
        return web.Response(text=f"Error reading image: {str(e)}", status=500)


@server.PromptServer.instance.routes.get("/video_scene/read_description")
async def read_scene_description(request):
    """
    API endpoint to read scene description files from ComfyUI output directory
    """
    filename = request.query.get("filename", "")
    subfolder = request.query.get("subfolder", "scene_outputs")
    
    if not filename:
        return web.Response(text="No filename provided", status=400)
    
    # Get ComfyUI output directory
    output_dir = folder_paths.get_output_directory()
    
    # Build file path
    file_path = os.path.join(output_dir, subfolder, filename)
    
    # Security check: ensure the file is within the output directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        return web.Response(text="Invalid file path", status=403)
    
    if not os.path.exists(file_path):
        return web.Response(text="Description not found", status=404)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(text=content, status=200)
    except Exception as e:
        return web.Response(text=f"Error reading description: {str(e)}", status=500)


@server.PromptServer.instance.routes.post("/video_scene/save_description")
async def save_scene_description(request):
    """
    API endpoint to save edited scene descriptions
    """
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    filename = data.get("filename", "")
    subfolder = data.get("subfolder", "scene_outputs")
    content = data.get("content", "")
    
    if not filename:
        return web.Response(text="No filename provided", status=400)
    
    # Validate filename
    if not filename.endswith('.txt'):
        return web.Response(text="Invalid file extension", status=400)
    
    # Get ComfyUI output directory
    output_dir = folder_paths.get_output_directory()
    
    # Build file path
    file_path = os.path.join(output_dir, subfolder, filename)
    
    # Security check: ensure the file is within the output directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        return web.Response(text="Invalid file path", status=403)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return web.json_response({
            "message": "Description saved successfully", 
            "filename": filename
        }, status=200)
    except Exception as e:
        return web.Response(text=f"Error saving description: {str(e)}", status=500)

@server.PromptServer.instance.routes.get("/video_scene/viewer/read_image")
async def viewer_read_image(request):
    """
    API endpoint to read scene image files from ANY directory
    (for VideoSceneViewer node)
    """
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    try:
        # Normalize the path to prevent directory traversal attacks
        filepath = os.path.normpath(filepath)
        
        # Security: Check if file exists and is readable
        if not os.path.exists(filepath):
            return web.Response(text="File not found", status=404)
        
        if not os.path.isfile(filepath):
            return web.Response(text="Not a file", status=400)
        
        # Check if it's an image file by extension
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        file_ext = os.path.splitext(filepath)[1].lower()
        
        if file_ext not in allowed_extensions:
            return web.Response(text="Not a supported image file", status=400)
        
        # Check file size (optional safety measure)
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            return web.Response(text="File too large", status=400)
        
        # Read the file
        with open(filepath, 'rb') as f:
            image_data = f.read()
        
        # Determine content type based on file extension
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        
        content_type = content_types.get(file_ext, 'application/octet-stream')
        
        return web.Response(body=image_data, content_type=content_type)
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except Exception as e:
        print(f"Error reading image {filepath}: {e}")
        return web.Response(text=f"Error reading image: {str(e)}", status=500)


@server.PromptServer.instance.routes.get("/video_scene/viewer/read_description")
async def viewer_read_description(request):
    """
    API endpoint to read scene description files from ANY directory
    (for VideoSceneViewer node)
    """
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    try:
        # Normalize the path
        filepath = os.path.normpath(filepath)
        
        # Security checks
        if not os.path.exists(filepath):
            return web.Response(text="File not found", status=404)
        
        if not os.path.isfile(filepath):
            return web.Response(text="Not a file", status=400)
        
        # Check if it's a text file
        if not filepath.lower().endswith('.txt'):
            return web.Response(text="Not a text file", status=400)
        
        # Check file size (text files should be small)
        file_size = os.path.getsize(filepath)
        if file_size > 10 * 1024 * 1024:  # 10MB limit for text files
            return web.Response(text="File too large", status=400)
        
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return web.Response(text=content, status=200)
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except UnicodeDecodeError:
        return web.Response(text="Invalid text encoding", status=400)
    except Exception as e:
        print(f"Error reading description {filepath}: {e}")
        return web.Response(text=f"Error reading description: {str(e)}", status=500)


@server.PromptServer.instance.routes.post("/video_scene/viewer/save_description")
async def viewer_save_description(request):
    """
    API endpoint to save edited scene descriptions to ANY directory
    (for VideoSceneViewer node)
    """
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    filepath = data.get("filepath", "")
    content = data.get("content", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    try:
        # Normalize the path
        filepath = os.path.normpath(filepath)
        
        # Validate filepath
        if not filepath.endswith('.txt'):
            return web.Response(text="Invalid file extension", status=400)
        
        # Security: Check parent directory exists and is writable
        parent_dir = os.path.dirname(filepath)
        if not os.path.exists(parent_dir):
            return web.Response(text="Parent directory does not exist", status=400)
        
        if not os.path.isdir(parent_dir):
            return web.Response(text="Parent is not a directory", status=400)
        
        # Check if we can write to the directory
        if not os.access(parent_dir, os.W_OK):
            return web.Response(text="Permission denied - cannot write to directory", status=403)
        
        # Optional: Limit content size
        if len(content.encode('utf-8')) > 5 * 1024 * 1024:  # 5MB limit
            return web.Response(text="Content too large", status=400)
        
        # Save the file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Saved description to: {filepath}")
        
        return web.json_response({
            "message": "Description saved successfully", 
            "filepath": filepath
        }, status=200)
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except Exception as e:
        print(f"Error saving description to {filepath}: {e}")
        return web.Response(text=f"Error saving description: {str(e)}", status=500)


# Optional: Add a route to check if a directory exists (for better UI feedback)
@server.PromptServer.instance.routes.get("/video_scene/viewer/check_directory")
async def viewer_check_directory(request):
    """
    API endpoint to check if a directory exists and is readable
    (for VideoSceneViewer node - optional)
    """
    directory = request.query.get("directory", "")
    
    if not directory:
        return web.Response(text="No directory provided", status=400)
    
    try:
        # Normalize the path
        directory = os.path.normpath(directory)
        
        if not os.path.exists(directory):
            return web.json_response({
                "exists": False,
                "readable": False,
                "message": "Directory does not exist"
            }, status=200)
        
        if not os.path.isdir(directory):
            return web.json_response({
                "exists": False,
                "readable": False,
                "message": "Path is not a directory"
            }, status=200)
        
        # Check if directory is readable
        readable = os.access(directory, os.R_OK)
        
        return web.json_response({
            "exists": True,
            "readable": readable,
            "message": "Directory exists" + ("" if readable else " but is not readable")
        }, status=200)
        
    except Exception as e:
        return web.json_response({
            "exists": False,
            "readable": False,
            "message": f"Error checking directory: {str(e)}"
        }, status=200)