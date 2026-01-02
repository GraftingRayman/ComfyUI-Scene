import os
import json
import server
from aiohttp import web
import folder_paths

# ==============================================================================
# SECURITY CONFIGURATION
# ==============================================================================
# Define allowed base directories for file access
# Users should configure this in a separate config file for their setup
def get_allowed_directories():
    """
    Get list of allowed directories for file access.
    This should be loaded from a configuration file in production.
    """
    allowed_dirs = []
    
    # Always allow ComfyUI output directory
    output_dir = folder_paths.get_output_directory()
    if output_dir:
        allowed_dirs.append(os.path.abspath(output_dir))
    
    # Allow ComfyUI input directory
    input_dir = folder_paths.get_input_directory()
    if input_dir:
        allowed_dirs.append(os.path.abspath(input_dir))
    
    # Check for custom config file
    config_path = os.path.join(os.path.dirname(__file__), "allowed_paths.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                custom_paths = config.get("allowed_directories", [])
                for path in custom_paths:
                    abs_path = os.path.abspath(os.path.expanduser(path))
                    if os.path.exists(abs_path) and os.path.isdir(abs_path):
                        allowed_dirs.append(abs_path)
                        print(f"Added allowed directory: {abs_path}")
                    else:
                        print(f"Warning: Directory not found or not accessible: {path}")
        except Exception as e:
            print(f"Warning: Could not load allowed_paths.json: {e}")
    else:
        print(f"Info: No allowed_paths.json found at {config_path}")
    
    print(f"Total allowed directories: {len(allowed_dirs)}")
    for d in allowed_dirs:
        print(f"  - {d}")
    
    return allowed_dirs

def is_path_allowed(filepath, allowed_directories):
    """
    Check if a filepath is within any of the allowed directories.
    Prevents path traversal attacks.
    """
    try:
        # Normalize and resolve the path
        abs_filepath = os.path.abspath(os.path.normpath(os.path.expanduser(filepath)))
        
        # Check if file exists
        if not os.path.exists(abs_filepath):
            return False, f"File not found: {abs_filepath}"
        
        # Check if it's actually a file
        if not os.path.isfile(abs_filepath):
            return False, "Not a file"
        
        # Check if path is within any allowed directory
        for allowed_dir in allowed_directories:
            try:
                # Use os.path.commonpath to check if file is under allowed directory
                common = os.path.commonpath([abs_filepath, allowed_dir])
                if common == allowed_dir:
                    print(f"Path allowed: {abs_filepath} (under {allowed_dir})")
                    return True, None
            except ValueError:
                # Different drives on Windows
                continue
        
        print(f"Path denied: {abs_filepath}")
        print(f"  Not in any of: {allowed_directories}")
        return False, "Path not in allowed directories"
        
    except Exception as e:
        return False, f"Path validation error: {str(e)}"

# ==============================================================================
# LEGACY ENDPOINTS (ComfyUI output directory only)
# ==============================================================================

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

# ==============================================================================
# SECURED VIEWER ENDPOINTS (Whitelist-based access)
# ==============================================================================

@server.PromptServer.instance.routes.get("/video_scene/viewer/read_image")
async def viewer_read_image(request):
    """
    SECURED: API endpoint to read scene image files from whitelisted directories
    """
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    # Get allowed directories
    allowed_dirs = get_allowed_directories()
    
    if not allowed_dirs:
        return web.Response(text="No allowed directories configured", status=500)
    
    # Validate path
    is_allowed, error_msg = is_path_allowed(filepath, allowed_dirs)
    if not is_allowed:
        return web.Response(text=f"Access denied: {error_msg}", status=403)
    
    try:
        # Check if it's an image file by extension
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        file_ext = os.path.splitext(filepath)[1].lower()
        
        if file_ext not in allowed_extensions:
            return web.Response(text="Not a supported image file", status=400)
        
        # Check file size (50MB limit)
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:
            return web.Response(text="File too large", status=400)
        
        # Read the file
        with open(filepath, 'rb') as f:
            image_data = f.read()
        
        # Determine content type
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
    SECURED: API endpoint to read text files from whitelisted directories
    """
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    # Get allowed directories
    allowed_dirs = get_allowed_directories()
    
    if not allowed_dirs:
        return web.Response(text="No allowed directories configured", status=500)
    
    # Validate path
    is_allowed, error_msg = is_path_allowed(filepath, allowed_dirs)
    if not is_allowed:
        return web.Response(text=f"Access denied: {error_msg}", status=403)
    
    try:
        # Check if it's a text file
        if not filepath.lower().endswith('.txt'):
            return web.Response(text="Not a text file", status=400)
        
        # Check file size (10MB limit for text files)
        file_size = os.path.getsize(filepath)
        if file_size > 10 * 1024 * 1024:
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
    SECURED: API endpoint to save text files to whitelisted directories
    """
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    filepath = data.get("filepath", "")
    content = data.get("content", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    # Get allowed directories
    allowed_dirs = get_allowed_directories()
    
    if not allowed_dirs:
        return web.Response(text="No allowed directories configured", status=500)
    
    try:
        # Normalize the path
        abs_filepath = os.path.abspath(os.path.normpath(os.path.expanduser(filepath)))
        
        # Validate file extension
        if not filepath.endswith('.txt'):
            return web.Response(text="Invalid file extension", status=400)
        
        # Check parent directory is in allowed list
        parent_dir = os.path.dirname(abs_filepath)
        parent_allowed = False
        
        for allowed_dir in allowed_dirs:
            try:
                common = os.path.commonpath([parent_dir, allowed_dir])
                if common == allowed_dir:
                    parent_allowed = True
                    break
            except ValueError:
                continue
        
        if not parent_allowed:
            return web.Response(text="Access denied: Parent directory not in allowed paths", status=403)
        
        # Check parent directory exists and is writable
        if not os.path.exists(parent_dir):
            return web.Response(text="Parent directory does not exist", status=400)
        
        if not os.path.isdir(parent_dir):
            return web.Response(text="Parent is not a directory", status=400)
        
        if not os.access(parent_dir, os.W_OK):
            return web.Response(text="Permission denied - cannot write to directory", status=403)
        
        # Limit content size (5MB)
        if len(content.encode('utf-8')) > 5 * 1024 * 1024:
            return web.Response(text="Content too large", status=400)
        
        # Save the file
        with open(abs_filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Saved description to: {abs_filepath}")
        
        return web.json_response({
            "message": "Description saved successfully", 
            "filepath": abs_filepath
        }, status=200)
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except Exception as e:
        print(f"Error saving description to {filepath}: {e}")
        return web.Response(text=f"Error saving description: {str(e)}", status=500)


@server.PromptServer.instance.routes.get("/video_scene/viewer/check_directory")
async def viewer_check_directory(request):
    """
    API endpoint to check if a directory exists and is in allowed paths
    """
    directory = request.query.get("directory", "")
    
    if not directory:
        return web.Response(text="No directory provided", status=400)
    
    # Get allowed directories
    allowed_dirs = get_allowed_directories()
    
    if not allowed_dirs:
        return web.json_response({
            "exists": False,
            "allowed": False,
            "readable": False,
            "message": "No allowed directories configured"
        }, status=200)
    
    try:
        # Normalize the path
        abs_directory = os.path.abspath(os.path.normpath(os.path.expanduser(directory)))
        
        if not os.path.exists(abs_directory):
            return web.json_response({
                "exists": False,
                "allowed": False,
                "readable": False,
                "message": "Directory does not exist"
            }, status=200)
        
        if not os.path.isdir(abs_directory):
            return web.json_response({
                "exists": False,
                "allowed": False,
                "readable": False,
                "message": "Path is not a directory"
            }, status=200)
        
        # Check if directory is in allowed paths
        is_allowed = False
        for allowed_dir in allowed_dirs:
            try:
                common = os.path.commonpath([abs_directory, allowed_dir])
                if common == allowed_dir:
                    is_allowed = True
                    break
            except ValueError:
                continue
        
        # Check if directory is readable
        readable = os.access(abs_directory, os.R_OK)
        
        message = "Directory exists"
        if not is_allowed:
            message += " but is not in allowed paths"
        elif not readable:
            message += " but is not readable"
        
        return web.json_response({
            "exists": True,
            "allowed": is_allowed,
            "readable": readable,
            "message": message
        }, status=200)
        
    except Exception as e:
        return web.json_response({
            "exists": False,
            "allowed": False,
            "readable": False,
            "message": f"Error checking directory: {str(e)}"
        }, status=200)