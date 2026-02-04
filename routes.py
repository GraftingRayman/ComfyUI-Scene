import os
import json
import server
from aiohttp import web
import folder_paths
import mimetypes
import urllib.parse

def get_scene_captions_dir(base_dir=None):
    """Get the scene captions directory path"""
    output_dir = folder_paths.get_output_directory()
    
    if base_dir and os.path.exists(base_dir):
        # Use provided base directory
        if "scene_outputs" in base_dir:
            # If base_dir already contains scene_outputs
            return os.path.join(base_dir, "scene_captions")
        else:
            # Add scene_outputs/scene_captions
            scene_outputs_dir = os.path.join(base_dir, "scene_outputs")
            return os.path.join(scene_outputs_dir, "scene_captions")
    else:
        # Default to output_dir/scene_outputs/scene_captions
        scene_outputs_dir = os.path.join(output_dir, "scene_outputs")
        return os.path.join(scene_outputs_dir, "scene_captions")

# ============ VIDEO SCENE EXTRACTOR ENDPOINTS ============
@server.PromptServer.instance.routes.get("/video_scene/read_image")
async def read_scene_image(request):
    filename = request.query.get("filename", "")
    subfolder = request.query.get("subfolder", "scene_outputs")
    
    if not filename:
        return web.Response(text="No filename provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    file_path = os.path.join(output_dir, subfolder, filename)
    
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        return web.Response(text="Invalid file path", status=403)
    
    if not os.path.exists(file_path):
        return web.Response(text="Image not found", status=404)
    
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
        return web.Response(text="Not an image file", status=400)
    
    try:
        with open(file_path, 'rb') as f:
            image_data = f.read()
        
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
    filename = request.query.get("filename", "")
    subfolder = request.query.get("subfolder", "scene_outputs")
    
    if not filename:
        return web.Response(text="No filename provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    file_path = os.path.join(output_dir, subfolder, filename)
    
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
    """Save description for VideoSceneExtractor (scene_outputs directory)"""
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    filename = data.get("filename", "")
    subfolder = data.get("subfolder", "scene_outputs")
    content = data.get("content", "")
    
    if not filename:
        return web.Response(text="No filename provided", status=400)
    
    if not filename.endswith('.txt'):
        return web.Response(text="Invalid file extension", status=400)
    
    output_dir = folder_paths.get_output_directory()
    file_path = os.path.join(output_dir, subfolder, filename)
    
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        return web.Response(text="Invalid file path", status=403)
    
    # Ensure subfolder exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return web.json_response({
            "message": "Description saved successfully", 
            "filename": filename,
            "filepath": file_path
        }, status=200)
    except Exception as e:
        return web.Response(text=f"Error saving description: {str(e)}", status=500)

# ============ VIDEO SCENE CAPTION ENDPOINTS ============
@server.PromptServer.instance.routes.post("/video_scene/caption/save")
async def caption_save_description(request):
    """Save caption description for VideoSceneCaption"""
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    filename = data.get("filename", "")
    scene_index = data.get("scene_index", -1)
    content = data.get("content", "")
    base_dir = data.get("base_dir", "")
    captions_dir = data.get("captions_dir", "")
    
    if not filename and scene_index < 0:
        return web.Response(text="No filename or scene index provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    # Determine the correct filename
    if not filename and scene_index >= 0:
        filename = f"scene_{scene_index:04d}_caption.txt"
    
    # Determine the correct directory
    if captions_dir:
        # Use provided captions directory
        file_path = os.path.join(captions_dir, filename)
    elif base_dir:
        # Use get_scene_captions_dir to determine the path
        captions_dir = get_scene_captions_dir(base_dir)
        file_path = os.path.join(captions_dir, filename)
    else:
        # Default to scene_outputs/scene_captions
        captions_dir = get_scene_captions_dir()
        file_path = os.path.join(captions_dir, filename)
    
    # Security check - must be within output directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        return web.Response(text="Invalid file path", status=403)
    
    # Ensure the captions directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return web.json_response({
            "message": "Caption saved successfully", 
            "filename": filename,
            "filepath": file_path,
            "scene_index": scene_index,
            "captions_dir": os.path.dirname(file_path)
        }, status=200)
    except Exception as e:
        return web.Response(text=f"Error saving caption: {str(e)}", status=500)

@server.PromptServer.instance.routes.get("/video_scene/caption/read")
async def caption_read_description(request):
    """Read caption description for VideoSceneCaption"""
    filename = request.query.get("filename", "")
    scene_index = request.query.get("scene_index", -1)
    captions_dir = request.query.get("captions_dir", "")
    
    if not filename and scene_index < 0:
        return web.Response(text="No filename or scene index provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    # Determine the correct filename
    if not filename and scene_index >= 0:
        filename = f"scene_{scene_index:04d}_caption.txt"
    
    # Determine the correct directory
    if captions_dir:
        # Use provided captions directory
        file_path = os.path.join(captions_dir, filename)
    else:
        # Default to scene_outputs/scene_captions
        captions_dir = get_scene_captions_dir()
        file_path = os.path.join(captions_dir, filename)
    
    # Security check - must be within output directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        return web.Response(text="Invalid file path", status=403)
    
    if not os.path.exists(file_path):
        return web.Response(text="Caption not found", status=404)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(text=content, status=200)
    except Exception as e:
        return web.Response(text=f"Error reading caption: {str(e)}", status=500)

# ============ ADDED MISSING ROUTE ============
@server.PromptServer.instance.routes.post("/video_scene/caption/save_description")
async def caption_save_direct(request):
    """Save caption description directly - endpoint for VideoSceneCaption.js"""
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    filepath = data.get("filepath", "")
    content = data.get("content", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    try:
        # Get absolute paths
        abs_filepath = os.path.abspath(filepath)
        abs_output_dir = os.path.abspath(output_dir)
        
        # Security check: file must be within output directory
        if not abs_filepath.startswith(abs_output_dir):
            return web.Response(text=f"Access denied: File must be within output directory", status=403)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(abs_filepath), exist_ok=True)
        
        # Save the content
        with open(abs_filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return web.json_response({
            "message": "Caption saved successfully",
            "filepath": abs_filepath,
            "directory": os.path.dirname(abs_filepath),
            "filename": os.path.basename(abs_filepath)
        }, status=200)
        
    except Exception as e:
        return web.Response(text=f"Error saving caption: {str(e)}", status=500)


@server.PromptServer.instance.routes.get("/video_scene/viewer/read_video")
async def viewer_read_video(request):
    """Serve video files for preview"""
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    # Get allowed directories
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    try:
        # Get absolute path
        decoded_path = urllib.parse.unquote(filepath)
        abs_filepath = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
        abs_output_dir = os.path.abspath(output_dir)
        
        # Security check - must be within output directory
        if not abs_filepath.startswith(abs_output_dir):
            return web.Response(text="Access denied: File not in output directory", status=403)
        
        # Check if file exists
        if not os.path.exists(abs_filepath):
            return web.Response(text="Video file not found", status=404)
        
        # Get file size
        file_size = os.path.getsize(abs_filepath)
        
        # Set reasonable limits
        max_size = 500 * 1024 * 1024  # 500MB
        if file_size > max_size:
            return web.Response(text=f"File too large ({file_size//(1024*1024)}MB > 500MB limit)", status=400)
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(abs_filepath)
        if not mime_type:
            mime_type = 'video/mp4'  # Default
        
        # Check if it's a video file
        if not mime_type.startswith('video/'):
            return web.Response(text="Not a video file", status=400)
        
        # Stream the file
        return web.FileResponse(
            abs_filepath,
            headers={
                'Content-Type': mime_type,
                'Accept-Ranges': 'bytes',
                'Content-Length': str(file_size),
                'Content-Disposition': f'inline; filename="{os.path.basename(abs_filepath)}"'
            }
        )
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except Exception as e:
        print(f"Error serving video {filepath}: {e}")
        return web.Response(text=f"Error reading video: {str(e)}", status=500)

@server.PromptServer.instance.routes.get("/video_scene/viewer/list_scene_videos")
async def list_scene_videos(request):
    """List all scene videos in a directory"""
    directory = request.query.get("directory", "")
    scene_index = request.query.get("scene_index", "")
    
    if not directory:
        return web.Response(text="No directory provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    try:
        decoded_path = urllib.parse.unquote(directory)
        abs_directory = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
        abs_output_dir = os.path.abspath(output_dir)
        
        # Check if directory is within output directory
        if not abs_directory.startswith(abs_output_dir):
            return web.Response(text="Access denied: Directory not in output directory", status=403)
        
        if not os.path.exists(abs_directory):
            return web.json_response({"videos": [], "error": "Directory not found"})
        
        if not os.path.isdir(abs_directory):
            return web.json_response({"videos": [], "error": "Not a directory"})
        
        # List video files
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}
        videos = []
        
        for filename in os.listdir(abs_directory):
            filepath = os.path.join(abs_directory, filename)
            if os.path.isfile(filepath):
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in video_extensions:
                    videos.append({
                        "filename": filename,
                        "filepath": filepath,
                        "size": os.path.getsize(filepath)
                    })
        
        # Sort by filename
        videos.sort(key=lambda x: x["filename"])
        
        # Filter by scene index if specified
        if scene_index:
            try:
                idx = int(scene_index)
                # Look for files with scene index pattern
                filtered = []
                for video in videos:
                    if f"scene_{idx:04d}" in video["filename"] or f"scene_{idx}" in video["filename"]:
                        filtered.append(video)
                videos = filtered
            except ValueError:
                pass
        
        return web.json_response({
            "directory": abs_directory,
            "total_videos": len(videos),
            "videos": videos
        })
        
    except Exception as e:
        return web.json_response({
            "videos": [],
            "error": f"Error listing videos: {str(e)}"
        })

@server.PromptServer.instance.routes.post("/video_scene/viewer/update_description")
async def viewer_update_description(request):
    """Update a scene description in metadata"""
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    metadata_file = data.get("metadata_file", "")
    scene_index = data.get("scene_index", 0)
    new_description = data.get("description", "")
    
    if not metadata_file:
        return web.Response(text="No metadata file provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    try:
        decoded_path = urllib.parse.unquote(metadata_file)
        abs_metadata_file = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
        abs_output_dir = os.path.abspath(output_dir)
        
        # Check if file is within output directory
        if not abs_metadata_file.startswith(abs_output_dir):
            return web.Response(text="Access denied", status=403)
        
        if not os.path.exists(abs_metadata_file):
            return web.Response(text="Metadata file not found", status=404)
        
        # Load metadata
        with open(abs_metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Update description
        if "scenes" in metadata and scene_index < len(metadata["scenes"]):
            metadata["scenes"][scene_index]["description"] = new_description
            
            # Also update description file if it exists
            scene_data = metadata["scenes"][scene_index]
            if "description_path" in scene_data and scene_data["description_path"]:
                desc_path = scene_data["description_path"]
                if os.path.exists(desc_path):
                    with open(desc_path, 'w', encoding='utf-8') as f:
                        f.write(new_description)
        
        # Save updated metadata
        with open(abs_metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return web.json_response({
            "success": True,
            "message": "Description updated"
        })
        
    except Exception as e:
        return web.Response(text=f"Error updating description: {str(e)}", status=500)

@server.PromptServer.instance.routes.get("/video_scene/viewer/check_file_exists")
async def check_file_exists(request):
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.json_response({"exists": False, "error": "No filepath provided"})
    
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.json_response({"exists": False, "error": "No output directory configured"})
    
    try:
        decoded_path = urllib.parse.unquote(filepath)
        abs_filepath = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
        abs_output_dir = os.path.abspath(output_dir)
        
        # Check if path is within output directory
        if not abs_filepath.startswith(abs_output_dir):
            return web.json_response({"exists": False, "error": "Path not in output directory"})
        
        exists = os.path.exists(abs_filepath)
        
        return web.json_response({
            "exists": exists,
            "filepath": abs_filepath,
            "is_file": os.path.isfile(abs_filepath) if exists else False,
            "size": os.path.getsize(abs_filepath) if exists and os.path.isfile(abs_filepath) else 0
        })
        
    except Exception as e:
        return web.json_response({"exists": False, "error": str(e)})

# ============ SIMPLER ENDPOINTS ============
@server.PromptServer.instance.routes.get("/video_scene/check_file")
async def check_video_file(request):
    """Simple endpoint to check if a video file exists"""
    path = request.query.get("path", "")
    
    if not path:
        return web.json_response({"exists": False})
    
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        exists = os.path.exists(abs_path) and os.path.isfile(abs_path)
        return web.json_response({"exists": exists, "path": abs_path})
    except:
        return web.json_response({"exists": False})

@server.PromptServer.instance.routes.get("/video_scene/read_video")
async def read_video_simple(request):
    """Simpler video endpoint"""
    path = request.query.get("path", "")
    
    if not path:
        return web.Response(text="No path provided", status=400)
    
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        
        # Basic security check
        output_dir = folder_paths.get_output_directory()
        if not abs_path.startswith(output_dir):
            return web.Response(text="Access denied", status=403)
        
        if not os.path.exists(abs_path):
            return web.Response(text="File not found", status=404)
        
        # Determine content type
        mime_type = "video/mp4"
        if abs_path.endswith('.webm'):
            mime_type = "video/webm"
        elif abs_path.endswith('.mov'):
            mime_type = "video/quicktime"
        elif abs_path.endswith('.avi'):
            mime_type = "video/x-msvideo"
        
        return web.FileResponse(abs_path, headers={'Content-Type': mime_type})
        
    except Exception as e:
        return web.Response(text=f"Error: {str(e)}", status=500)

# ============ DEBUG ENDPOINTS ============
@server.PromptServer.instance.routes.get("/video_scene/debug/video_access")
async def debug_video_access(request):
    """Debug endpoint to test video file access"""
    test_path = request.query.get("path", "")
    
    if not test_path:
        return web.json_response({"error": "No path provided"})
    
    # Try different variations
    decoded_path = urllib.parse.unquote(test_path)
    abs_path = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
    
    # Check if file exists
    exists = os.path.exists(abs_path)
    
    # Get output directory
    output_dir = folder_paths.get_output_directory()
    abs_output_dir = os.path.abspath(output_dir) if output_dir else None
    
    # Check if path is within output directory
    is_in_output_dir = abs_output_dir and abs_path.startswith(abs_output_dir)
    
    # Try to construct URL
    relative_url = None
    if is_in_output_dir:
        rel_path = os.path.relpath(abs_path, abs_output_dir)
        relative_url = f"/video_scene/read_video?path={urllib.parse.quote(rel_path)}"
    
    full_url = f"/video_scene/viewer/read_video?filepath={urllib.parse.quote(abs_path)}"
    
    return web.json_response({
        "test_path": test_path,
        "decoded_path": decoded_path,
        "absolute_path": abs_path,
        "exists": exists,
        "is_file": os.path.isfile(abs_path) if exists else False,
        "output_directory": output_dir,
        "is_in_output_dir": is_in_output_dir,
        "relative_url": relative_url,
        "full_url": full_url,
        "suggested_url": full_url if is_in_output_dir else relative_url
    })

@server.PromptServer.instance.routes.get("/video_scene/debug/captions_dir")
async def debug_captions_dir(request):
    """Debug endpoint to get scene captions directory"""
    base_dir = request.query.get("base_dir", "")
    
    captions_dir = get_scene_captions_dir(base_dir if base_dir else None)
    
    return web.json_response({
        "base_dir": base_dir,
        "captions_dir": captions_dir,
        "exists": os.path.exists(captions_dir),
        "is_dir": os.path.isdir(captions_dir) if os.path.exists(captions_dir) else False
    })

# ============ VIDEO SCENE VIEWER ENDPOINTS ============
@server.PromptServer.instance.routes.get("/video_scene/viewer/read_image")
async def viewer_read_image(request):
    """Read image for VideoSceneViewer with full path support"""
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    try:
        # Get absolute path
        decoded_path = urllib.parse.unquote(filepath)
        abs_filepath = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
        abs_output_dir = os.path.abspath(output_dir)
        
        # Security check - must be within output directory
        if not abs_filepath.startswith(abs_output_dir):
            return web.Response(text="Access denied: File not in output directory", status=403)
        
        # Check if file exists
        if not os.path.exists(abs_filepath):
            return web.Response(text="Image not found", status=404)
        
        # Check if it's an image file
        if not abs_filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif')):
            return web.Response(text="Not an image file", status=400)
        
        # Determine content type
        mime_type, _ = mimetypes.guess_type(abs_filepath)
        if not mime_type:
            if abs_filepath.lower().endswith('.png'):
                mime_type = 'image/png'
            elif abs_filepath.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif abs_filepath.lower().endswith('.gif'):
                mime_type = 'image/gif'
            elif abs_filepath.lower().endswith('.bmp'):
                mime_type = 'image/bmp'
            elif abs_filepath.lower().endswith('.webp'):
                mime_type = 'image/webp'
            elif abs_filepath.lower().endswith(('.tiff', '.tif')):
                mime_type = 'image/tiff'
            else:
                mime_type = 'application/octet-stream'
        
        # Read and return the image
        with open(abs_filepath, 'rb') as f:
            image_data = f.read()
        
        return web.Response(body=image_data, content_type=mime_type)
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except Exception as e:
        print(f"Error reading image {filepath}: {e}")
        return web.Response(text=f"Error reading image: {str(e)}", status=500)

@server.PromptServer.instance.routes.get("/video_scene/viewer/read_description")
async def viewer_read_description(request):
    """Read description for VideoSceneViewer with full path support"""
    filepath = request.query.get("filepath", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    try:
        # Get absolute path
        decoded_path = urllib.parse.unquote(filepath)
        abs_filepath = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
        abs_output_dir = os.path.abspath(output_dir)
        
        # Security check - must be within output directory
        if not abs_filepath.startswith(abs_output_dir):
            return web.Response(text="Access denied: File not in output directory", status=403)
        
        # Check if file exists
        if not os.path.exists(abs_filepath):
            return web.Response(text="Description file not found", status=404)
        
        # Read and return the content
        with open(abs_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return web.Response(text=content, status=200)
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except UnicodeDecodeError:
        return web.Response(text="File encoding error", status=500)
    except Exception as e:
        print(f"Error reading description {filepath}: {e}")
        return web.Response(text=f"Error reading description: {str(e)}", status=500)

@server.PromptServer.instance.routes.post("/video_scene/viewer/save_description")
async def viewer_save_description(request):
    """Save description for VideoSceneViewer with full path support"""
    try:
        data = await request.json()
    except:
        return web.Response(text="Invalid JSON", status=400)
    
    filepath = data.get("filepath", "")
    content = data.get("content", "")
    
    if not filepath:
        return web.Response(text="No filepath provided", status=400)
    
    output_dir = folder_paths.get_output_directory()
    if not output_dir:
        return web.Response(text="No output directory configured", status=500)
    
    try:
        # Get absolute path
        decoded_path = urllib.parse.unquote(filepath)
        abs_filepath = os.path.abspath(os.path.normpath(os.path.expanduser(decoded_path)))
        abs_output_dir = os.path.abspath(output_dir)
        
        # Security check - must be within output directory
        if not abs_filepath.startswith(abs_output_dir):
            return web.Response(text="Access denied: File not in output directory", status=403)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(abs_filepath), exist_ok=True)
        
        # Save the content
        with open(abs_filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return web.json_response({
            "message": "Description saved successfully",
            "filepath": abs_filepath,
            "directory": os.path.dirname(abs_filepath),
            "filename": os.path.basename(abs_filepath)
        }, status=200)
        
    except PermissionError:
        return web.Response(text="Permission denied", status=403)
    except Exception as e:
        print(f"Error saving description to {filepath}: {e}")
        return web.Response(text=f"Error saving description: {str(e)}", status=500)