#!/usr/bin/env python3
"""
Godot MCP Enhanced Server
A comprehensive MCP server for Godot Engine with advanced features for Windsurf AI
"""

import asyncio
import json
import os
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Configuration
GODOT_HOST = os.getenv("GODOT_HOST", "127.0.0.1")
GODOT_PORT = int(os.getenv("GDAI_MCP_SERVER_PORT", "3571"))
GODOT_BASE_URL = f"http://{GODOT_HOST}:{GODOT_PORT}"

# Initialize MCP server
app = Server("godot-mcp-enhanced")

# Cache for the Godot project path (fetched once from running Godot)
_godot_project_path: Optional[str] = None


async def resolve_res_path(res_path: str) -> str:
    """Convert a res:// path to an absolute filesystem path using Godot's project_path."""
    global _godot_project_path
    if not res_path.startswith("res://"):
        return res_path
    if _godot_project_path is None:
        try:
            result = await call_godot_api("/api/project/info")
            _godot_project_path = result.get("data", {}).get("project_path", "")
        except Exception:
            _godot_project_path = ""
    if _godot_project_path:
        return os.path.join(_godot_project_path, res_path[len("res://"):])
    # Fallback: strip res:// and use CWD
    return res_path.replace("res://", "./")


async def to_res_path(path: str) -> str:
    """Convert an absolute or relative path to res:// when under the Godot project root."""
    global _godot_project_path
    if not path:
        return path
    if path.startswith("res://"):
        return path
    if _godot_project_path is None:
        try:
            result = await call_godot_api("/api/project/info")
            _godot_project_path = result.get("data", {}).get("project_path", "")
        except Exception:
            _godot_project_path = ""
    if _godot_project_path:
        root = os.path.realpath(_godot_project_path)
        full = os.path.realpath(path)
        if full == root or full.startswith(root + os.sep):
            rel = os.path.relpath(full, root).replace("\\", "/")
            return "res://" + rel
    return path


async def call_godot_api(endpoint: str, params: dict = None) -> dict:
    """
    Call Godot HTTP API endpoint with error handling
    """
    url = f"{GODOT_BASE_URL}{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=params or {})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP error calling Godot API: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error calling Godot API: {str(e)}"
        }


async def notify_godot_filesystem_scan() -> None:
    """Ask the editor to rescan so externally written files appear. Best-effort."""
    try:
        await call_godot_api("/api/qa/reimport_all", {"force_reimport": False})
    except Exception:
        pass


def _format_project_godot_value(value) -> str:
    """Serialize a Python value to a project.godot assignment RHS."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        # Allow callers to pass pre-formatted Godot expressions
        if (
            stripped.startswith("PackedStringArray(")
            or stripped.startswith("Vector")
            or stripped.startswith("Color(")
            or (stripped.startswith('"') and stripped.endswith('"'))
        ):
            return stripped
        return json.dumps(value)
    return json.dumps(str(value))


def _update_project_godot_file(settings_file: str, settings: dict) -> list:
    """Section-aware update of project.godot. Returns list of updated keys.

    ProjectSettings paths like 'application/config/name' map to:
      [application]
      config/name="..."
    """
    with open(settings_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Index sections: section_name -> {header_idx, keys: {file_key: line_idx}}
    sections: dict = {}
    current_section = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[/"):
            current_section = stripped[1:-1]
            if current_section not in sections:
                sections[current_section] = {"header_idx": i, "keys": {}}
            continue
        if current_section is None or not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        if "=" in stripped:
            file_key = stripped.split("=", 1)[0].strip()
            sections[current_section]["keys"][file_key] = i

    updated = []
    # Defer insertions so line indices stay valid while we rewrite existing keys
    insertions: list[tuple[int, str]] = []  # (insert_after_line, new_line)

    for full_key, value in settings.items():
        full_key = str(full_key)
        if "/" not in full_key:
            # Treat as key under [application] if no section separator
            section_name, file_key = "application", full_key
        else:
            section_name, file_key = full_key.split("/", 1)

        rhs = _format_project_godot_value(value)
        new_line = f"{file_key}={rhs}\n"

        if section_name in sections and file_key in sections[section_name]["keys"]:
            idx = sections[section_name]["keys"][file_key]
            lines[idx] = new_line
            updated.append(full_key)
            continue

        if section_name in sections:
            # Insert after last key in section, or right after header if empty
            sec = sections[section_name]
            if sec["keys"]:
                insert_after = max(sec["keys"].values())
            else:
                insert_after = sec["header_idx"]
            insertions.append((insert_after, new_line))
            updated.append(full_key)
            continue

        # Create new section at end of file
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"
        lines.append("\n")
        lines.append(f"[{section_name}]\n")
        new_header_idx = len(lines) - 1
        lines.append(new_line)
        sections[section_name] = {
            "header_idx": new_header_idx,
            "keys": {file_key: len(lines) - 1},
        }
        updated.append(full_key)

    # Apply insertions from bottom to top so indices remain valid
    for insert_after, new_line in sorted(insertions, key=lambda t: t[0], reverse=True):
        lines.insert(insert_after + 1, new_line)

    with open(settings_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return updated


# ===== TOOL DEFINITIONS =====

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools"""
    return [
        # Project Tools
        Tool(
            name="get_project_info",
            description="Get information about the Godot project including name, version, and settings",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_filesystem_tree",
            description="Get a recursive tree view of all files and directories in the project",
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to filter (e.g., ['.gd', '.tscn'])"
                    }
                }
            }
        ),
        Tool(
            name="search_files",
            description="Search for files in the project using fuzzy matching",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="uid_to_project_path",
            description="Convert a Godot UID (uid://) to a project path (res://)",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "UID string (e.g., 'uid://abc123')"
                    }
                },
                "required": ["uid"]
            }
        ),
        Tool(
            name="project_path_to_uid",
            description="Convert a project path (res://) to a Godot UID",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project path (e.g., 'res://scenes/main.tscn')"
                    }
                },
                "required": ["path"]
            }
        ),
        
        # Scene Tools
        Tool(
            name="get_scene_tree",
            description="Get a recursive tree view of all nodes in the current scene with properties",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_scene_file_content",
            description="Get the raw content of the current scene file",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="create_scene",
            description="Create a new scene with a specified root node type",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Path where scene will be saved (relative to res://)"
                    },
                    "root_type": {
                        "type": "string",
                        "description": "Type of root node (e.g., 'Node2D', 'Node3D', 'Control')",
                        "default": "Node2D"
                    }
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="open_scene",
            description="Open a scene in the Godot editor",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Path to the scene file"
                    }
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="delete_scene",
            description="Delete a scene file from the project",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Path to the scene file to delete"
                    }
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="add_scene",
            description="Add a scene as a child node to the current scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Path to the scene to add"
                    },
                    "parent_node": {
                        "type": "string",
                        "description": "Path to parent node (leave empty for root)"
                    }
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="play_scene",
            description="Play the current scene or a specific scene in Godot",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Optional: specific scene to play (empty for current)"
                    }
                }
            }
        ),
        Tool(
            name="stop_running_scene",
            description="Stop the currently running scene in Godot",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        
        # Node Tools
        Tool(
            name="add_node",
            description="Add a new node to the current scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_type": {
                        "type": "string",
                        "description": "Type of node to add (e.g., 'Sprite2D', 'RigidBody2D')"
                    },
                    "node_name": {
                        "type": "string",
                        "description": "Name for the new node"
                    },
                    "parent_node_path": {
                        "type": "string",
                        "description": "Path to parent node (empty for root)"
                    },
                    "properties": {
                        "type": "object",
                        "description": "Properties to set on the node"
                    }
                },
                "required": ["node_type", "node_name"]
            }
        ),
        Tool(
            name="delete_node",
            description="Delete a node from the current scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node to delete"
                    }
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="duplicate_node",
            description="Duplicate an existing node in the scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node to duplicate"
                    }
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="move_node",
            description="Move a node to a different parent in the scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node to move"
                    },
                    "new_parent_path": {
                        "type": "string",
                        "description": "Path to the new parent node"
                    }
                },
                "required": ["node_path", "new_parent_path"]
            }
        ),
        Tool(
            name="update_property",
            description="Update a property of a node in the scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node"
                    },
                    "property": {
                        "type": "string",
                        "description": "Property name to update"
                    },
                    "value": {
                        "description": "New value for the property"
                    }
                },
                "required": ["node_path", "property", "value"]
            }
        ),
        Tool(
            name="add_resource",
            description="Add a resource to a node property (e.g., Shape to CollisionShape)",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node"
                    },
                    "resource_type": {
                        "type": "string",
                        "description": "Type of resource (e.g., 'RectangleShape2D')"
                    },
                    "property": {
                        "type": "string",
                        "description": "Property to assign resource to"
                    },
                    "resource_properties": {
                        "type": "object",
                        "description": "Properties to set on the resource"
                    }
                },
                "required": ["node_path", "resource_type", "property"]
            }
        ),
        Tool(
            name="set_anchor_preset",
            description="Set anchor preset for a Control node",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the Control node"
                    },
                    "preset": {
                        "type": "string",
                        "description": "Preset name (e.g., 'center', 'full_rect', 'top_left')"
                    }
                },
                "required": ["node_path", "preset"]
            }
        ),
        Tool(
            name="set_anchor_values",
            description="Set precise anchor values for a Control node",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the Control node"
                    },
                    "anchor_left": {"type": "number"},
                    "anchor_top": {"type": "number"},
                    "anchor_right": {"type": "number"},
                    "anchor_bottom": {"type": "number"}
                },
                "required": ["node_path"]
            }
        ),
        
        # Script Tools
        Tool(
            name="get_open_scripts",
            description="Get a list of all scripts open in the editor with their contents",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="view_script",
            description="View and activate a script in the editor",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path to the script file"
                    }
                },
                "required": ["script_path"]
            }
        ),
        Tool(
            name="create_script",
            description="Create a new GDScript file",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path where script will be saved"
                    },
                    "content": {
                        "type": "string",
                        "description": "Script content"
                    },
                    "base_type": {
                        "type": "string",
                        "description": "Base class (e.g., 'Node', 'CharacterBody2D')",
                        "default": "Node"
                    }
                },
                "required": ["script_path"]
            }
        ),
        Tool(
            name="attach_script",
            description="Attach a script to a node in the scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node"
                    },
                    "script_path": {
                        "type": "string",
                        "description": "Path to the script file"
                    }
                },
                "required": ["node_path", "script_path"]
            }
        ),
        Tool(
            name="edit_file",
            description="Edit a file using find and replace",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file"
                    },
                    "find": {
                        "type": "string",
                        "description": "Text to find"
                    },
                    "replace": {
                        "type": "string",
                        "description": "Text to replace with"
                    },
                    "regex": {
                        "type": "boolean",
                        "description": "Use regex for find/replace"
                    }
                },
                "required": ["file_path", "find", "replace"]
            }
        ),
        
        # Editor Tools
        Tool(
            name="get_godot_errors",
            description="Get all errors from Godot including script errors, runtime errors, and logs",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_editor_screenshot",
            description="Capture a screenshot of the Godot editor window (returns base64-encoded PNG)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_running_scene_screenshot",
            description="Capture a screenshot of the running game window (returns base64-encoded PNG)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="execute_editor_script",
            description="Execute arbitrary GDScript code in the editor context",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "GDScript code to execute"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="clear_output_logs",
            description="Clear the output logs in the Godot editor",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        
        # Windsurf-Specific Tools
        Tool(
            name="get_windsurf_context",
            description="Get comprehensive context about the current Godot project state for AI understanding",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_live_preview",
            description="Get live preview including screenshot, scene tree, and current script for Windsurf",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        
        # Godot Process Management Tools
        Tool(
            name="check_godot_running",
            description="Check if Godot editor is currently running and responsive",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="launch_godot",
            description="Launch Godot editor with the current project. Requires GODOT_EXECUTABLE environment variable to be set.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Godot project directory (containing project.godot)"
                    },
                    "editor_mode": {
                        "type": "boolean",
                        "description": "Launch in editor mode (true) or run the project (false)",
                        "default": True
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="get_godot_version",
            description="Get the version of Godot that is configured or running",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        
        # Direct File System Tools (work without Godot running)
        Tool(
            name="read_scene_file",
            description="Read and parse a .tscn scene file directly from the file system",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Path to the scene file (res:// or absolute path)"
                    }
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="write_scene_file",
            description="Write a .tscn scene file directly to the file system",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {
                        "type": "string",
                        "description": "Path where the scene file will be saved"
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete .tscn file content"
                    }
                },
                "required": ["scene_path", "content"]
            }
        ),
        Tool(
            name="read_script_file",
            description="Read a .gd script file directly from the file system",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path to the script file"
                    }
                },
                "required": ["script_path"]
            }
        ),
        Tool(
            name="write_script_file",
            description="Write a .gd script file directly to the file system",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path where the script file will be saved"
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete script content"
                    }
                },
                "required": ["script_path", "content"]
            }
        ),
        Tool(
            name="read_project_settings",
            description="Read project.godot settings file",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project directory"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="update_project_settings",
            description="Update specific settings in project.godot file",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project directory"
                    },
                    "settings": {
                        "type": "object",
                        "description": "Settings to update (e.g., {'application/config/name': 'My Game'})"
                    }
                },
                "required": ["project_path", "settings"]
            }
        ),
        Tool(
            name="create_directory",
            description="Create a directory in the project",
            inputSchema={
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Path to the directory to create"
                    }
                },
                "required": ["dir_path"]
            }
        ),
        Tool(
            name="list_directory",
            description="List contents of a directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Path to the directory"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively",
                        "default": False
                    }
                },
                "required": ["dir_path"]
            }
        ),
        
        # Runtime Operations Tools
        Tool(
            name="simulate_key_press",
            description="Simulate keyboard key press for testing gameplay",
            inputSchema={
                "type": "object",
                "properties": {
                    "keycode": {
                        "type": "integer",
                        "description": "Key code to simulate (e.g., 32 for Space, 87 for W)"
                    },
                    "pressed": {
                        "type": "boolean",
                        "description": "Whether key is pressed (true) or released (false)",
                        "default": True
                    }
                },
                "required": ["keycode"]
            }
        ),
        Tool(
            name="simulate_action",
            description="Simulate input action (like jump, move_left, etc.) for testing",
            inputSchema={
                "type": "object",
                "properties": {
                    "action_name": {
                        "type": "string",
                        "description": "Name of the input action (e.g., 'ui_accept', 'jump', 'move_left')"
                    },
                    "pressed": {
                        "type": "boolean",
                        "description": "Whether action is pressed or released",
                        "default": True
                    },
                    "strength": {
                        "type": "number",
                        "description": "Action strength (0.0 to 1.0)",
                        "default": 1.0
                    }
                },
                "required": ["action_name"]
            }
        ),
        Tool(
            name="get_runtime_stats",
            description="Get real-time performance statistics (FPS, memory, draw calls, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_node_properties",
            description="Get all properties of a node at runtime for debugging",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node (e.g., 'Player', 'Player/Sprite2D')"
                    }
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="call_node_method",
            description="Call a method on a node for testing or debugging",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to the node"
                    },
                    "method_name": {
                        "type": "string",
                        "description": "Name of the method to call"
                    },
                    "args": {
                        "type": "array",
                        "description": "Arguments to pass to the method",
                        "default": []
                    }
                },
                "required": ["node_path", "method_name"]
            }
        ),
        Tool(
            name="get_installed_plugins",
            description="Get list of all installed Godot plugins",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_plugin_info",
            description="Get detailed information about a specific plugin",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "Name of the plugin folder"
                    }
                },
                "required": ["plugin_name"]
            }
        ),
        Tool(
            name="get_assets_by_type",
            description="Get all assets of a specific type (texture, mesh, audio, script, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "asset_type": {
                        "type": "string",
                        "description": "Type of assets to find",
                        "enum": ["texture", "image", "mesh", "model", "3d", "audio", "sound", "script", "scene", "material", "shader"]
                    }
                },
                "required": ["asset_type"]
            }
        ),
        Tool(
            name="get_asset_info",
            description="Get detailed information about a specific asset",
            inputSchema={
                "type": "object",
                "properties": {
                    "asset_path": {
                        "type": "string",
                        "description": "Path to the asset file"
                    }
                },
                "required": ["asset_path"]
            }
        ),
        Tool(
            name="run_test_script",
            description="Execute a test script and return results",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path": {
                        "type": "string",
                        "description": "Path to the test script file"
                    }
                },
                "required": ["script_path"]
            }
        ),
        Tool(
            name="get_input_actions",
            description="Get all registered input actions and their key bindings",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # New Scene Tools
        Tool(
            name="save_scene",
            description="Save the current open scene to disk. IMPORTANT: Call this after making node/property changes to persist them.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="rename_node",
            description="Rename a node in the current scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the node (e.g., 'Player' or 'Player/Sprite2D')"},
                    "new_name": {"type": "string", "description": "New name for the node"}
                },
                "required": ["node_path", "new_name"]
            }
        ),
        Tool(
            name="reorder_node",
            description="Move a node to a specific child index within its parent (affects draw order and processing order)",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the node"},
                    "new_index": {"type": "integer", "description": "New child index (0 = first)"}
                },
                "required": ["node_path", "new_index"]
            }
        ),
        Tool(
            name="find_nodes",
            description="Find all nodes in the current scene matching a type and/or name pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_type": {"type": "string", "description": "Godot class name to filter by (e.g., 'Sprite2D', 'CharacterBody2D'). Empty = any type."},
                    "name_pattern": {"type": "string", "description": "Name glob pattern (e.g., 'Enemy*', 'Player'). Empty = any name."}
                },
                "required": []
            }
        ),
        Tool(
            name="get_node_signals",
            description="List all signals available on a node and its current signal connections",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the node"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="connect_signal",
            description="Connect a signal from a source node to a method on a target node",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_node_path": {"type": "string", "description": "Path to the node emitting the signal"},
                    "signal_name": {"type": "string", "description": "Name of the signal to connect (e.g., 'body_entered', 'pressed', 'timeout')"},
                    "target_node_path": {"type": "string", "description": "Path to the node that handles the signal"},
                    "method_name": {"type": "string", "description": "Method name on the target node to call (e.g., '_on_body_entered')"}
                },
                "required": ["source_node_path", "signal_name", "target_node_path", "method_name"]
            }
        ),
        Tool(
            name="disconnect_signal",
            description="Disconnect a signal connection between two nodes",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_node_path": {"type": "string"},
                    "signal_name": {"type": "string"},
                    "target_node_path": {"type": "string"},
                    "method_name": {"type": "string"}
                },
                "required": ["source_node_path", "signal_name", "target_node_path", "method_name"]
            }
        ),
        Tool(
            name="add_to_group",
            description="Add a node to a named group (persistent - saved in scene file). Groups enable calling methods on all group members at once.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the node"},
                    "group_name": {"type": "string", "description": "Group name (e.g., 'enemies', 'collectibles', 'player')"}
                },
                "required": ["node_path", "group_name"]
            }
        ),
        Tool(
            name="remove_from_group",
            description="Remove a node from a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"},
                    "group_name": {"type": "string"}
                },
                "required": ["node_path", "group_name"]
            }
        ),
        Tool(
            name="get_node_groups",
            description="Get all groups a node belongs to",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="batch_set_properties",
            description="Set multiple properties on multiple nodes in a single call. More efficient than repeated update_property calls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "description": "List of {node_path, property, value} operations",
                        "items": {
                            "type": "object",
                            "properties": {
                                "node_path": {"type": "string"},
                                "property": {"type": "string"},
                                "value": {"description": "The value to set"}
                            },
                            "required": ["node_path", "property", "value"]
                        }
                    }
                },
                "required": ["operations"]
            }
        ),
        Tool(
            name="get_class_property_list",
            description="Get all available properties for a Godot class by name. Use this to discover what properties you can set on a node type before using add_node or update_property.",
            inputSchema={
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Godot class name (e.g., 'CharacterBody2D', 'Sprite2D', 'Label')"}
                },
                "required": ["class_name"]
            }
        ),

        # Autoload / Project Configuration Tools
        Tool(
            name="get_autoloads",
            description="List all autoload singletons configured in the project (Project Settings > Globals > Autoload)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="add_autoload",
            description="Add an autoload singleton to the project. These are globally accessible scripts (e.g., GameManager, AudioManager).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Singleton name used to access it (e.g., 'GameManager')"},
                    "path": {"type": "string", "description": "Path to the GDScript file (e.g., 'res://scripts/game_manager.gd')"},
                    "singleton": {"type": "boolean", "description": "Make it a singleton (true) or just autoloaded (false). Default: true", "default": True}
                },
                "required": ["name", "path"]
            }
        ),
        Tool(
            name="remove_autoload",
            description="Remove an autoload singleton from the project",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the autoload to remove"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="set_main_scene",
            description="Set the project's main scene (the scene that runs when you press Play or export the game)",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string", "description": "Path to the scene file (e.g., 'res://scenes/main.tscn')"}
                },
                "required": ["scene_path"]
            }
        ),

        # ── Import Settings ───────────────────────────────────────────────────
        Tool(
            name="get_import_settings",
            description=(
                "Read the current .import settings for an asset (texture, audio, model, etc). "
                "Returns all sections including [params] which controls compression, mipmaps, "
                "normal map flag, etc. Use before set_import_settings to see available keys."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_path": {
                        "type": "string",
                        "description": "res:// path to the asset (e.g. 'res://sprites/player.png')"
                    }
                },
                "required": ["resource_path"]
            }
        ),
        Tool(
            name="set_import_settings",
            description=(
                "Update .import settings for an asset and trigger a reimport. "
                "Common texture params: compress/mode (0=lossless,1=lossy,2=vram_compressed), "
                "compress/normal_map (0=disabled,1=enabled), mipmaps/generate (true/false). "
                "Call get_import_settings first to discover available param names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_path": {
                        "type": "string",
                        "description": "res:// path to the asset"
                    },
                    "params": {
                        "type": "object",
                        "description": "Key-value pairs to set in the [params] section of the .import file",
                        "additionalProperties": True
                    }
                },
                "required": ["resource_path", "params"]
            }
        ),

        # ── Undo / Redo ───────────────────────────────────────────────────────
        Tool(
            name="undo",
            description=(
                "Undo the last editor action in the current scene's undo history. "
                "Works on actions recorded by Godot's EditorUndoRedoManager."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="redo",
            description=(
                "Redo the last undone editor action in the current scene's undo history."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),

        # ── Navigation ────────────────────────────────────────────────────────
        Tool(
            name="bake_navigation_mesh",
            description=(
                "Bake NavigationMesh/NavigationPolygon for NavigationRegion3D or NavigationRegion2D nodes. "
                "If node_path is omitted, finds and bakes ALL navigation regions in the scene. "
                "Must have a NavigationMesh/NavigationPolygon resource assigned to the region first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {
                        "type": "string",
                        "description": "Path to a specific NavigationRegion2D/3D. Omit to bake all."
                    }
                },
                "required": []
            }
        ),

        # ── Profiler ──────────────────────────────────────────────────────────
        Tool(
            name="get_profiler_snapshot",
            description=(
                "Sample Godot Performance monitors over N frames and return avg/min/max stats. "
                "Metrics: fps, process_ms, physics_ms, draw_calls, nodes, objects, memory_mb, video_mem_mb. "
                "Run while a scene is playing for game-specific data. Includes automatic bottleneck warnings."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "frame_count": {
                        "type": "integer",
                        "description": "Number of frames to sample (1–300, default 60 = ~1 second at 60fps)",
                        "default": 60
                    }
                },
                "required": []
            }
        ),

        # ── Previously wired but missing Tool() definitions ───────────────────
        Tool(
            name="get_node_methods",
            description="Get all script-defined methods on a node. Useful before calling call_node_method.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the node"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="simulate_mouse_button",
            description="Simulate a mouse button press or release at a screen position while the game is running",
            inputSchema={
                "type": "object",
                "properties": {
                    "button_index": {"type": "integer", "description": "Mouse button: 1=left, 2=right, 3=middle"},
                    "pressed": {"type": "boolean", "description": "True to press, false to release", "default": True},
                    "position_x": {"type": "number", "description": "X screen coordinate"},
                    "position_y": {"type": "number", "description": "Y screen coordinate"}
                },
                "required": ["button_index"]
            }
        ),
        Tool(
            name="simulate_mouse_motion",
            description="Simulate mouse movement to a screen position while the game is running",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_x": {"type": "number", "description": "Target X screen coordinate"},
                    "position_y": {"type": "number", "description": "Target Y screen coordinate"},
                    "relative_x": {"type": "number", "description": "Relative X movement delta", "default": 0},
                    "relative_y": {"type": "number", "description": "Relative Y movement delta", "default": 0}
                },
                "required": ["position_x", "position_y"]
            }
        ),

        # ── Export Tools ──────────────────────────────────────────────────────
        Tool(
            name="get_export_presets",
            description=(
                "Read all export presets from export_presets.cfg. "
                "Returns preset names, platforms, output paths, and options. "
                "You must have at least one preset configured in Godot (Project → Export) before calling export_project."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Absolute path to the Godot project folder. Defaults to current working directory."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="export_project",
            description=(
                "Export the Godot project for a target platform using a named export preset. "
                "Requires GODOT_EXECUTABLE env var and an existing export preset (see get_export_presets). "
                "Runs: godot --headless --export-release '<preset_name>' '<output_path>'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "preset_name": {
                        "type": "string",
                        "description": "Exact preset name from export_presets.cfg (e.g. 'Windows Desktop', 'HTML5', 'Android')"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output file path (e.g. '/tmp/game.exe', '/tmp/game.html', '/tmp/game.apk')"
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Absolute path to Godot project folder. Defaults to current working directory."
                    },
                    "debug": {
                        "type": "boolean",
                        "description": "Export a debug build (--export-debug) instead of release. Default: false.",
                        "default": False
                    }
                },
                "required": ["preset_name", "output_path"]
            }
        ),

        Tool(
            name="create_export_preset",
            description=(
                "Create a new export preset entry in export_presets.cfg. "
                "Supported platforms: 'Windows Desktop', 'Linux/X11', 'macOS', 'Web', 'Android', 'iOS'. "
                "After creating, open Godot to configure export templates, then use export_project."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "preset_name": {
                        "type": "string",
                        "description": "Display name for this preset (e.g. 'Windows Release')"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Target platform. Must match a Godot export platform name exactly."
                    },
                    "export_path": {
                        "type": "string",
                        "description": "Default output file path (e.g. 'builds/game.exe', 'builds/game.html')",
                        "default": ""
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Absolute path to the Godot project folder. Defaults to cwd."
                    },
                    "runnable": {
                        "type": "boolean",
                        "description": "Mark as the runnable preset for this platform (default: true)",
                        "default": True
                    },
                    "options": {
                        "type": "object",
                        "description": "Additional platform-specific options to write into [preset.N.options]",
                        "additionalProperties": True,
                        "default": {}
                    }
                },
                "required": ["preset_name", "platform"]
            }
        ),

        # ── Shader / Material Tools ───────────────────────────────────────────
        Tool(
            name="set_shader_parameter",
            description=(
                "Set a parameter on a ShaderMaterial attached to a node. "
                "Works with MeshInstance3D, Sprite2D, CanvasItem material_override, etc. "
                "The material must already be a ShaderMaterial (not StandardMaterial3D)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Scene-tree path to the node (e.g. 'MeshInstance3D' or 'Player/Body')"},
                    "param_name": {"type": "string", "description": "Shader uniform name as declared in the .gdshader file"},
                    "value": {"description": "Value to set. For vec2/vec3/vec4 use arrays [x,y,z,w]. For colors use [r,g,b,a]."},
                    "surface_index": {"type": "integer", "description": "For MeshInstance3D: which surface's material (default 0)", "default": 0}
                },
                "required": ["node_path", "param_name", "value"]
            }
        ),

        # ── Resource Health Tools ─────────────────────────────────────────────
        Tool(
            name="scan_broken_resources",
            description=(
                "Scan the entire project for broken resource references — "
                "res:// paths mentioned in .tscn/.tres/.res files that no longer exist on disk. "
                "Returns a list of {file, missing_ref} pairs. Run after moving/renaming files."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),

        # ── TileMap Tools ─────────────────────────────────────────────────────
        Tool(
            name="paint_tiles",
            description=(
                "Paint multiple cells on a TileMap layer in one call. "
                "Each cell: {x, y, source_id, atlas_x, atlas_y, alternative_tile}. "
                "You can set default source_id/atlas_x/atlas_y at the top level for uniform tiles. "
                "Adds layers automatically if needed. Use for placing floors, walls, decorations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":         {"type": "string",  "description": "Path to the TileMap node"},
                    "layer":             {"type": "integer", "description": "Layer index (default: 0)"},
                    "cells":             {"type": "array",   "description": "Array of cell objects: [{x, y, source_id?, atlas_x?, atlas_y?, alternative_tile?}]"},
                    "source_id":         {"type": "integer", "description": "Default TileSet source ID for all cells (default: 0)"},
                    "atlas_x":           {"type": "integer", "description": "Default atlas X coordinate"},
                    "atlas_y":           {"type": "integer", "description": "Default atlas Y coordinate"},
                    "alternative_tile":  {"type": "integer", "description": "Default alternative tile index"}
                },
                "required": ["node_path", "cells"]
            }
        ),
        Tool(
            name="fill_tiles_rect",
            description="Fill a rectangular region of a TileMap layer with a single tile. Specify top-left corner (x,y), width, height, and the tile (source_id, atlas_x, atlas_y).",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":        {"type": "string",  "description": "Path to the TileMap node"},
                    "layer":            {"type": "integer", "description": "Layer index (default: 0)"},
                    "x":                {"type": "integer", "description": "Left edge cell X"},
                    "y":                {"type": "integer", "description": "Top edge cell Y"},
                    "width":            {"type": "integer", "description": "Width in cells"},
                    "height":           {"type": "integer", "description": "Height in cells"},
                    "source_id":        {"type": "integer", "description": "TileSet source ID"},
                    "atlas_x":          {"type": "integer", "description": "Atlas X coordinate"},
                    "atlas_y":          {"type": "integer", "description": "Atlas Y coordinate"},
                    "alternative_tile": {"type": "integer", "description": "Alternative tile index (default: 0)"}
                },
                "required": ["node_path", "width", "height"]
            }
        ),
        Tool(
            name="clear_tiles",
            description="Erase specific cells from a TileMap layer, or clear an entire layer if no cells are specified.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string",  "description": "Path to the TileMap node"},
                    "layer":     {"type": "integer", "description": "Layer index (default: 0)"},
                    "cells":     {"type": "array",   "description": "Cells to erase [{x, y}]. Omit to clear entire layer."}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="get_cell_tile",
            description="Get the tile data (source_id, atlas coords, alternative_tile) at a specific TileMap cell position.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string",  "description": "Path to the TileMap node"},
                    "layer":     {"type": "integer", "description": "Layer index (default: 0)"},
                    "x":         {"type": "integer", "description": "Cell X coordinate"},
                    "y":         {"type": "integer", "description": "Cell Y coordinate"}
                },
                "required": ["node_path", "x", "y"]
            }
        ),

        # ── GridMap Tools ──────────────────────────────────────────────────────
        Tool(
            name="set_grid_cell",
            description="Set a single GridMap cell to an item from the MeshLibrary. Use item_id=-1 to erase. Orientation 0–23 controls the 24 possible rotations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":   {"type": "string",  "description": "Path to the GridMap node"},
                    "x":           {"type": "integer", "description": "Cell X coordinate"},
                    "y":           {"type": "integer", "description": "Cell Y (vertical)"},
                    "z":           {"type": "integer", "description": "Cell Z coordinate"},
                    "item_id":     {"type": "integer", "description": "MeshLibrary item ID (-1 to erase)"},
                    "orientation": {"type": "integer", "description": "Rotation index 0–23 (default: 0)"}
                },
                "required": ["node_path", "x", "y", "z", "item_id"]
            }
        ),
        Tool(
            name="fill_grid_box",
            description="Fill a 3D box region of a GridMap with a single mesh item. Use for building floors (y=0, height=1), walls, platforms, or entire rooms.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":   {"type": "string",  "description": "Path to the GridMap node"},
                    "x":           {"type": "integer", "description": "Start X"},
                    "y":           {"type": "integer", "description": "Start Y"},
                    "z":           {"type": "integer", "description": "Start Z"},
                    "width":       {"type": "integer", "description": "X extent (cells)"},
                    "height":      {"type": "integer", "description": "Y extent (cells)"},
                    "depth":       {"type": "integer", "description": "Z extent (cells)"},
                    "item_id":     {"type": "integer", "description": "MeshLibrary item ID"},
                    "orientation": {"type": "integer", "description": "Rotation index 0–23 (default: 0)"}
                },
                "required": ["node_path", "width", "height", "depth", "item_id"]
            }
        ),
        Tool(
            name="get_grid_used_cells",
            description="List all occupied cells in a GridMap with their item IDs, orientations, and MeshLibrary item names (if available).",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the GridMap node"}
                },
                "required": ["node_path"]
            }
        ),

        # ── Batch Operation Tools ──────────────────────────────────────────────
        Tool(
            name="batch_set_property_on_type",
            description="Set a property on every node of a given Godot class in the current scene. Use for: set all Light3D energy to 1.5, enable all CollisionShape3D, configure all AudioStreamPlayer3D buses.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_type": {"type": "string", "description": "Godot class name (e.g. 'Light3D', 'CollisionShape3D', 'MeshInstance3D')"},
                    "property":  {"type": "string", "description": "Property name to set"},
                    "value":     {"description": "New value (arrays are coerced to Vector2/3/Color)"}
                },
                "required": ["node_type", "property", "value"]
            }
        ),
        Tool(
            name="batch_set_property_on_group",
            description="Set a property on every node belonging to a named group in the current scene. Use for groups like 'enemies', 'collectibles', 'platforms'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {"type": "string", "description": "Group name to target"},
                    "property":   {"type": "string", "description": "Property name to set"},
                    "value":      {"description": "New value"}
                },
                "required": ["group_name", "property", "value"]
            }
        ),
        Tool(
            name="replace_in_all_scripts",
            description=(
                "Find & replace text or regex across all .gd script files in the project. "
                "Supports dry_run mode to preview changes. Set include_addons=true to also scan addons/. "
                "Use for: rename a function everywhere, update a deprecated API call, fix a typo across all scripts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "search":          {"type": "string",  "description": "Text or regex pattern to search for"},
                    "replacement":     {"type": "string",  "description": "Replacement text (use $1/$2 for regex groups)"},
                    "use_regex":       {"type": "boolean", "description": "Treat search as a regex pattern (default: false)"},
                    "dry_run":         {"type": "boolean", "description": "Preview changes without writing files (default: false)"},
                    "include_addons":  {"type": "boolean", "description": "Also scan addons/ directory (default: false)"}
                },
                "required": ["search", "replacement"]
            }
        ),
        Tool(
            name="batch_create_nodes",
            description=(
                "Create multiple nodes in one call. Ideal for scaffolding entire systems in a single request. "
                "Each entry: {type, name, parent_path, properties: {key: value}, script: 'res://...'}. "
                "Array property values are coerced to Vector2/Vector3/Color automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "description": "Array of node specs",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type":        {"type": "string", "description": "Godot class name"},
                                "name":        {"type": "string", "description": "Node name"},
                                "parent_path": {"type": "string", "description": "Parent path (default: scene root)"},
                                "properties":  {"type": "object", "description": "Property key→value pairs"},
                                "script":      {"type": "string", "description": "res:// path to attach script"}
                            }
                        }
                    }
                },
                "required": ["nodes"]
            }
        ),

        # ── Animation Extra Tools ──────────────────────────────────────────────
        Tool(
            name="add_blend_space_point",
            description=(
                "Add an animation blend point to an AnimationNodeBlendSpace1D or BlendSpace2D "
                "that is a state inside an AnimationNodeStateMachine. "
                "For 1D: blend_position is a float. For 2D: blend_position is [x, y]. "
                "Use to build locomotion blending (idle/walk/run/sprint at different speeds)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tree_path":       {"type": "string", "description": "Path to the AnimationTree node"},
                    "state_name":      {"type": "string", "description": "Name of the BlendSpace state in the StateMachine"},
                    "animation_name":  {"type": "string", "description": "Animation to play at this blend point"},
                    "blend_position":  {"description": "Float for 1D, [x, y] array for 2D blend space"}
                },
                "required": ["state_name", "animation_name", "blend_position"]
            }
        ),
        Tool(
            name="get_blend_space_info",
            description="Get all blend points, positions, limits, and snap settings from an AnimationNodeBlendSpace1D or BlendSpace2D state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tree_path":  {"type": "string", "description": "Path to the AnimationTree node"},
                    "state_name": {"type": "string", "description": "Name of the blend space state"}
                },
                "required": ["state_name"]
            }
        ),
        Tool(
            name="copy_animation",
            description=(
                "Copy animations from one AnimationPlayer to another (deep-copy — players are independent after). "
                "Specify animation_names to copy specific ones, or omit to copy all. "
                "Use dest_library_name to organize copied animations into a named library."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source_player_path": {"type": "string", "description": "Path to source AnimationPlayer"},
                    "dest_player_path":   {"type": "string", "description": "Path to destination AnimationPlayer"},
                    "animation_names":    {"type": "array",  "items": {"type": "string"}, "description": "Specific animation names to copy (omit to copy all)"},
                    "dest_library_name":  {"type": "string", "description": "Destination library name (default: '' = default library)"}
                },
                "required": ["source_player_path", "dest_player_path"]
            }
        ),
        Tool(
            name="set_animation_speed_scale",
            description="Set the playback speed_scale on an AnimationPlayer. 1.0=normal, 2.0=double speed, 0.5=slow motion, 0=freeze.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":  {"type": "string", "description": "Path to the AnimationPlayer node"},
                    "speed_scale":  {"type": "number", "description": "Playback speed multiplier (default: 1.0)"}
                },
                "required": ["speed_scale"]
            }
        ),

        # ── QA / Validation Tools ──────────────────────────────────────────────
        Tool(
            name="assert_no_errors",
            description="Assert that the Godot error log contains no errors. Returns {passed, error_count, errors}. Use in automated test chains after scene setup or gameplay simulation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_warnings": {"type": "boolean", "description": "Also fail if warnings exist (default: false)"}
                }
            }
        ),
        Tool(
            name="validate_scene",
            description=(
                "Validate the current scene for common issues. Checks: "
                "CollisionShape nodes missing shape resources, physics bodies without collision, "
                "MeshInstance3D without mesh, AnimationTree pointing to invalid player, "
                "Area nodes without collision shapes, lights with unusually high energy. "
                "Returns {passed, error_count, warning_count, findings}."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="simulate_mouse_path",
            description="Simulate mouse movement along an array of screen positions with configurable interval. Optionally click at the final position. Use for testing UI drag operations, drawing tools, or camera controls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "points":       {"type": "array",   "description": "Array of {x, y} positions to move through"},
                    "interval_ms":  {"type": "integer", "description": "Milliseconds between each move step (default: 50)"},
                    "click_at_end": {"type": "boolean", "description": "Click at the final position (default: false)"},
                    "button_index": {"type": "integer", "description": "Mouse button for click (1=left, 2=right, default: 1)"}
                },
                "required": ["points"]
            }
        ),
        Tool(
            name="reimport_all",
            description="Trigger a full filesystem scan so Godot detects and reimports changed assets. Set force_reimport=true to force reimport of all known assets (slower but thorough).",
            inputSchema={
                "type": "object",
                "properties": {
                    "force_reimport": {"type": "boolean", "description": "Force reimport all assets, not just changed ones (default: false)"}
                }
            }
        ),
        Tool(
            name="set_node_unique_name",
            description="Set or clear the unique_name_in_owner flag on a node, enabling %NodeName shorthand access from scripts (node.get_node('%MyNode')). Use after creating important singleton-like nodes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string",  "description": "Path to the node"},
                    "unique":    {"type": "boolean", "description": "True to enable unique name, false to disable (default: true)"}
                },
                "required": ["node_path"]
            }
        ),

        # ── Audio Tools ───────────────────────────────────────────────────────
        Tool(
            name="create_audio_player_3d",
            description=(
                "Create an AudioStreamPlayer3D node at a 3D position with a loaded audio stream. "
                "Configures unit_size, max_distance, volume_db, pitch_scale, bus, attenuation_model "
                "(inverse_distance/inverse_square/logarithmic/disabled), and autoplay. "
                "Use for footsteps, gunshots, ambient sounds, or any positional 3D audio."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parent_path":        {"type": "string",  "description": "Parent node path"},
                    "player_name":        {"type": "string",  "description": "Node name (default: AudioStreamPlayer3D)"},
                    "stream_path":        {"type": "string",  "description": "res:// path to the audio file (.wav, .ogg, .mp3)"},
                    "position":           {"type": "array",   "items": {"type": "number"}, "description": "3D position [x, y, z]"},
                    "volume_db":          {"type": "number",  "description": "Volume in decibels (default: 0.0)"},
                    "pitch_scale":        {"type": "number",  "description": "Pitch multiplier (default: 1.0)"},
                    "unit_size":          {"type": "number",  "description": "Reference distance for attenuation (default: 10.0)"},
                    "max_distance":       {"type": "number",  "description": "Max audible distance (default: 0 = unlimited)"},
                    "bus":                {"type": "string",  "description": "Target audio bus name (default: Master)"},
                    "autoplay":           {"type": "boolean", "description": "Play on scene start"},
                    "attenuation_model":  {"type": "string",  "description": "inverse_distance / inverse_square / logarithmic / disabled"},
                    "play_immediately":   {"type": "boolean", "description": "Call play() right after creation (default: false)"},
                    "max_polyphony":      {"type": "integer", "description": "Max simultaneous voices (default: 1)"}
                }
            }
        ),
        Tool(
            name="play_audio",
            description="Play or resume an AudioStreamPlayer (2D, 3D, or non-spatial) from an optional position in the stream.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":      {"type": "string", "description": "Path to the AudioStreamPlayer node"},
                    "from_position":  {"type": "number", "description": "Start position in seconds (default: 0.0)"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="stop_audio",
            description="Stop playback on an AudioStreamPlayer (2D, 3D, or non-spatial).",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the AudioStreamPlayer node"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="set_audio_property",
            description="Set a property on an AudioStreamPlayer. Common: volume_db, pitch_scale, bus, unit_size, max_distance, autoplay, stream_paused, max_polyphony, panning_strength.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the AudioStreamPlayer node"},
                    "property":  {"type": "string", "description": "Property name"},
                    "value":     {"description": "New property value"}
                },
                "required": ["node_path", "property", "value"]
            }
        ),
        Tool(
            name="get_playback_position",
            description="Get current playback position, is_playing state, volume_db, pitch_scale, and stream path from an AudioStreamPlayer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the AudioStreamPlayer node"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="set_bus_volume",
            description="Set the volume_db on a named AudioServer bus (Master, Music, SFX, etc.). Use for game-wide volume control or muting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bus_name":  {"type": "string", "description": "Bus name (default: Master)"},
                    "volume_db": {"type": "number", "description": "Volume in decibels (0 = unity, -80 = silent, +6 = louder)"}
                },
                "required": ["volume_db"]
            }
        ),
        Tool(
            name="add_bus_effect",
            description=(
                "Add an AudioEffect to an AudioServer bus. "
                "Effect types: AudioEffectReverb, AudioEffectDelay, AudioEffectCompressor, "
                "AudioEffectLimiter, AudioEffectDistortion, AudioEffectChorus, AudioEffectPitchShift, "
                "AudioEffectAmplify, AudioEffectEQ6/EQ10/EQ21. "
                "Additional params (e.g. room_size, dry, wet for reverb) are applied automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "bus_name":    {"type": "string", "description": "Target bus name (default: Master)"},
                    "effect_type": {"type": "string", "description": "AudioEffect class name (e.g. AudioEffectReverb)"}
                },
                "required": ["effect_type"]
            }
        ),

        # ── Testing / QA Tools ─────────────────────────────────────────────────
        Tool(
            name="simulate_action_sequence",
            description=(
                "Execute a sequence of input actions/keypresses with configurable delays — "
                "for automated playtesting. Each step: "
                "{action: 'jump', pressed: true, delay_ms: 200} or "
                "{keycode: 32, pressed: true, delay_ms: 100}. "
                "Use to test walk→jump→attack combos, UI navigation, or ragdoll triggers."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "description": "Array of input steps",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action":   {"type": "string",  "description": "Input action name (from InputMap)"},
                                "keycode":  {"type": "integer", "description": "Raw keycode (alternative to action)"},
                                "pressed":  {"type": "boolean", "description": "True=press, False=release (default: true)"},
                                "delay_ms": {"type": "integer", "description": "Wait this many ms AFTER firing (default: 0)"},
                                "strength": {"type": "number",  "description": "Action strength 0–1 (default: 1.0)"}
                            }
                        }
                    }
                },
                "required": ["steps"]
            }
        ),
        Tool(
            name="wait_frames",
            description="Await N process frames (or physics frames) before returning. Use after physics operations to let simulation settle before asserting results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "frame_count":    {"type": "integer", "description": "Number of frames to wait (default: 10, max: 300)"},
                    "physics_frames": {"type": "boolean", "description": "Wait for physics frames instead of process frames (default: false)"}
                }
            }
        ),
        Tool(
            name="assert_node_property",
            description="Assert that a node's property matches an expected value. Returns {passed, actual, expected}. Supports numeric tolerance for floats and Vector3 distance for positions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":      {"type": "string",  "description": "Path to the node"},
                    "property":       {"type": "string",  "description": "Property name to check"},
                    "expected_value": {"description": "Expected value (number, bool, string, or [x,y,z] for Vector3)"},
                    "tolerance":      {"type": "number",  "description": "Tolerance for numeric/Vector3 comparison (default: 0.001)"}
                },
                "required": ["node_path", "property", "expected_value"]
            }
        ),
        Tool(
            name="capture_frame_sequence",
            description="Capture N editor screenshots with a configurable interval between them. Returns array of base64-encoded PNGs. Use for before/after comparisons, animation verification, particle reviews.",
            inputSchema={
                "type": "object",
                "properties": {
                    "frame_count":   {"type": "integer", "description": "Number of screenshots to capture (default: 3, max: 10)"},
                    "interval_ms":   {"type": "integer", "description": "Milliseconds between captures (default: 500)"},
                    "capture_game":  {"type": "boolean", "description": "Capture game viewport instead of editor window (default: false)"}
                }
            }
        ),
        Tool(
            name="get_scene_statistics",
            description="Count all nodes in the current scene by type. Returns total node count, script count, max depth, and a sorted type breakdown. Use for QA audits and performance baselines.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),

        # ── Editor Polish Tools ────────────────────────────────────────────────
        Tool(
            name="select_nodes",
            description="Select one or more nodes in the editor viewport by their scene paths. Clears existing selection by default. Useful for then inspecting or batch-editing selected nodes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_paths":     {"type": "array",   "items": {"type": "string"}, "description": "List of node paths to select"},
                    "clear_existing": {"type": "boolean", "description": "Clear current selection first (default: true)"}
                },
                "required": ["node_paths"]
            }
        ),
        Tool(
            name="batch_duplicate_with_offset",
            description=(
                "Duplicate a node N times, each copy offset by a cumulative position and/or rotation delta. "
                "Perfect for placing fence posts, pillars, trees, enemy spawn points, or any repeating level geometry. "
                "Works for both Node3D (3D offset) and Node2D (2D offset)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":          {"type": "string",  "description": "Source node path to duplicate"},
                    "count":              {"type": "integer", "description": "Number of duplicates to create (default: 2, max: 100)"},
                    "position_offset":    {"type": "array",   "items": {"type": "number"}, "description": "Per-copy position delta [x, y, z] (default: [1, 0, 0])"},
                    "rotation_offset_deg":{"type": "array",   "items": {"type": "number"}, "description": "Per-copy rotation delta in degrees [x, y, z]"},
                    "name_prefix":        {"type": "string",  "description": "Name prefix for duplicates (default: source node name)"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="find_scripts_with_pattern",
            description=(
                "Grep all .gd script files in the project for a regex pattern. "
                "Use to find: all scripts extending a class ('extends CharacterBody3D'), "
                "all scripts calling a method ('apply_impulse'), or all usage of a node type. "
                "Returns file paths, line numbers, and matching text (up to 5 matches per file)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern":     {"type": "string",  "description": "Regex pattern to search for"},
                    "max_results": {"type": "integer", "description": "Max matching files to return (default: 50)"}
                },
                "required": ["pattern"]
            }
        ),

        # ── Physics Tools ─────────────────────────────────────────────────────
        Tool(
            name="apply_impulse",
            description="Apply an instant impulse to a RigidBody3D (immediate velocity change — use for hits, explosions, jumps). Requires game to be playing for visible effect.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string",  "description": "Path to the RigidBody3D node"},
                    "impulse":   {"type": "array",   "items": {"type": "number"}, "description": "Impulse vector [x, y, z]"},
                    "position":  {"type": "array",   "items": {"type": "number"}, "description": "Application point relative to body center [x, y, z] (default: [0,0,0])"}
                },
                "required": ["node_path", "impulse"]
            }
        ),
        Tool(
            name="apply_force",
            description="Apply a continuous force to a RigidBody3D each physics frame. For one-time hits, prefer apply_impulse.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the RigidBody3D node"},
                    "force":     {"type": "array",  "items": {"type": "number"}, "description": "Force vector [x, y, z]"},
                    "position":  {"type": "array",  "items": {"type": "number"}, "description": "Application point [x, y, z] (default: [0,0,0])"}
                },
                "required": ["node_path", "force"]
            }
        ),
        Tool(
            name="apply_torque",
            description="Apply a rotational torque to a RigidBody3D (causes spinning). Use for doors, ragdoll limbs, barrels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the RigidBody3D node"},
                    "torque":    {"type": "array",  "items": {"type": "number"}, "description": "Torque vector [x, y, z]"}
                },
                "required": ["node_path", "torque"]
            }
        ),
        Tool(
            name="set_linear_velocity",
            description="Directly set linear_velocity on a RigidBody3D or CharacterBody3D. Use for launching projectiles, teleporting with momentum, or resetting velocity to zero.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the physics body node"},
                    "velocity":  {"type": "array",  "items": {"type": "number"}, "description": "Velocity vector [x, y, z]"}
                },
                "required": ["node_path", "velocity"]
            }
        ),
        Tool(
            name="set_angular_velocity",
            description="Directly set angular_velocity on a RigidBody3D. Use for spinning objects, ragdoll setup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the RigidBody3D node"},
                    "velocity":  {"type": "array",  "items": {"type": "number"}, "description": "Angular velocity [x, y, z] in radians/sec"}
                },
                "required": ["node_path", "velocity"]
            }
        ),
        Tool(
            name="set_physics_property",
            description=(
                "Set a physics property on any physics body node. "
                "Common properties: mass (float), gravity_scale (float), linear_damp (float), "
                "angular_damp (float), freeze (bool), freeze_mode (string: static/kinematic), "
                "collision_layer (int or [layer_numbers]), collision_mask (int or [layer_numbers]), "
                "can_sleep (bool), continuous_cd (bool), max_contacts_reported (int)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the physics body node"},
                    "property":  {"type": "string", "description": "Property name (e.g. 'mass', 'gravity_scale', 'freeze_mode')"},
                    "value":     {"description": "New value (type depends on property)"}
                },
                "required": ["node_path", "property", "value"]
            }
        ),
        Tool(
            name="create_joint",
            description=(
                "Create a physics joint node and wire two bodies together. "
                "Joint types: HingeJoint3D (doors, hinges), PinJoint3D (ragdoll shoulder/hip), "
                "SliderJoint3D (pistons, elevators), Generic6DOFJoint3D (full 6-axis control), "
                "ConeTwistJoint3D (ball socket, spine). "
                "Set node_a_path and node_b_path to the two RigidBody3D paths to connect."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_type":   {"type": "string", "description": "HingeJoint3D / PinJoint3D / SliderJoint3D / Generic6DOFJoint3D / ConeTwistJoint3D"},
                    "parent_path":  {"type": "string", "description": "Parent node path (default: scene root)"},
                    "joint_name":   {"type": "string", "description": "Name for the joint node"},
                    "node_a_path":  {"type": "string", "description": "Path to first RigidBody3D"},
                    "node_b_path":  {"type": "string", "description": "Path to second RigidBody3D"},
                    "position":     {"type": "array",  "items": {"type": "number"}, "description": "Joint position [x, y, z]"}
                },
                "required": ["joint_type"]
            }
        ),

        # ── Particle Tools ────────────────────────────────────────────────────
        Tool(
            name="create_particles",
            description=(
                "Create a GPUParticles3D node with a fully configured ParticleProcessMaterial in one call. "
                "Supports: amount, lifetime, one_shot, explosiveness, emission_shape (point/sphere/box/ring), "
                "emission_sphere_radius, gravity [x,y,z], initial_velocity_min/max, scale_min/max, color [r,g,b,a], "
                "direction [x,y,z], spread (degrees), linear_accel_min/max, position [x,y,z]. "
                "Use for muzzle flash, blood splatter, magic effects, fire, smoke, rain."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parent_path":          {"type": "string",  "description": "Parent node path"},
                    "particle_name":        {"type": "string",  "description": "Node name (default: GPUParticles3D)"},
                    "amount":               {"type": "integer", "description": "Max simultaneous particles (default: 100)"},
                    "lifetime":             {"type": "number",  "description": "Particle lifetime in seconds (default: 1.0)"},
                    "one_shot":             {"type": "boolean", "description": "Emit once then stop (default: false)"},
                    "explosiveness":        {"type": "number",  "description": "0=spread out, 1=all at once (default: 0)"},
                    "emission_shape":       {"type": "string",  "description": "point / sphere / box / ring (default: point)"},
                    "emission_sphere_radius": {"type": "number","description": "Sphere emission radius"},
                    "emission_box_extents": {"type": "array",   "items": {"type": "number"}, "description": "Box extents [x,y,z]"},
                    "gravity":              {"type": "array",   "items": {"type": "number"}, "description": "Gravity [x,y,z] (default: [0,-9.8,0])"},
                    "initial_velocity_min": {"type": "number",  "description": "Min emission speed"},
                    "initial_velocity_max": {"type": "number",  "description": "Max emission speed"},
                    "direction":            {"type": "array",   "items": {"type": "number"}, "description": "Emission direction [x,y,z]"},
                    "spread":               {"type": "number",  "description": "Spread angle in degrees"},
                    "scale_min":            {"type": "number",  "description": "Min particle scale"},
                    "scale_max":            {"type": "number",  "description": "Max particle scale"},
                    "color":                {"type": "array",   "items": {"type": "number"}, "description": "Particle color [r,g,b,a]"},
                    "position":             {"type": "array",   "items": {"type": "number"}, "description": "Node position [x,y,z]"},
                    "linear_accel_min":     {"type": "number",  "description": "Min linear acceleration"},
                    "linear_accel_max":     {"type": "number",  "description": "Max linear acceleration"}
                }
            }
        ),
        Tool(
            name="set_particle_material_param",
            description=(
                "Set a specific parameter on an existing GPUParticles3D's ParticleProcessMaterial. "
                "Common params: emission_shape (string: point/sphere/box/ring), emission_sphere_radius, "
                "initial_velocity_min, initial_velocity_max, gravity [x,y,z], direction [x,y,z], "
                "spread, color [r,g,b,a], scale_min, scale_max, linear_accel_min/max, "
                "radial_accel_min/max, tangential_accel_min/max, lifetime_randomness."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":  {"type": "string", "description": "Path to the GPUParticles3D node"},
                    "param_name": {"type": "string", "description": "ParticleProcessMaterial property name"},
                    "value":      {"description": "New value (number, bool, or array for Vector3/Color)"}
                },
                "required": ["node_path", "param_name", "value"]
            }
        ),
        Tool(
            name="restart_particles",
            description="Restart a GPUParticles3D or CPUParticles3D emission from scratch. Sets emitting=true after restart.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the particle node"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="get_particle_info",
            description="Get all properties of a GPUParticles3D node including amount, lifetime, emission state, and ParticleProcessMaterial settings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the GPUParticles3D node"}
                },
                "required": ["node_path"]
            }
        ),

        # ── Shader Tools ──────────────────────────────────────────────────────
        Tool(
            name="create_shader_material",
            description=(
                "Create a new ShaderMaterial with given GLSL shader code and assign it to a node's material slot. "
                "Start code with 'shader_type spatial;' for 3D or 'shader_type canvas_item;' for 2D. "
                "Use for damage glow, dissolve effects, hologram, outline, animated wind, water ripples."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":    {"type": "string",  "description": "Path to the node to assign the material to"},
                    "shader_code":  {"type": "string",  "description": "Full Godot shader source code"},
                    "surface_slot": {"type": "integer", "description": "Surface/material slot index (default: 0)"}
                },
                "required": ["node_path", "shader_code"]
            }
        ),
        Tool(
            name="get_shader_code",
            description="Read the current GLSL shader source code from a node's ShaderMaterial.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":    {"type": "string",  "description": "Path to the node"},
                    "surface_slot": {"type": "integer", "description": "Surface slot (default: 0)"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="set_shader_code",
            description="Hot-reload the shader source code on a node's ShaderMaterial. Creates a new ShaderMaterial if none exists. Godot recompiles the shader immediately.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":    {"type": "string",  "description": "Path to the node"},
                    "shader_code":  {"type": "string",  "description": "New shader source code"},
                    "surface_slot": {"type": "integer", "description": "Surface slot (default: 0)"}
                },
                "required": ["node_path", "shader_code"]
            }
        ),
        Tool(
            name="get_shader_parameters",
            description="List all uniforms declared in a node's ShaderMaterial shader, with current values. Use this before set_shader_parameter to see what parameters exist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":    {"type": "string",  "description": "Path to the node"},
                    "surface_slot": {"type": "integer", "description": "Surface slot (default: 0)"}
                },
                "required": ["node_path"]
            }
        ),

        # ── Animation Tools ───────────────────────────────────────────────────
        Tool(
            name="get_animation_player_info",
            description="List all animation libraries and animations in an AnimationPlayer node. Returns current animation, play state, and all library/animation names with length and track counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path": {"type": "string", "description": "Path to AnimationPlayer node (default: 'AnimationPlayer')"}
                }
            }
        ),
        Tool(
            name="create_animation",
            description="Create a new Animation resource and add it to an AnimationPlayer's library. Specify length, loop mode (none/linear/pingpong), and step.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":      {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name":   {"type": "string",  "description": "Name for the new animation"},
                    "library_name":     {"type": "string",  "description": "Library to add to (default: '' = default library)"},
                    "length":           {"type": "number",  "description": "Animation length in seconds (default: 1.0)"},
                    "loop_mode":        {"type": "string",  "description": "Loop mode: none / linear / pingpong (default: none)"},
                    "step":             {"type": "number",  "description": "Step size (default: 0.1)"}
                },
                "required": ["animation_name"]
            }
        ),
        Tool(
            name="get_animation_info",
            description="Get detailed info about an animation: length, loop mode, step, and a list of all tracks with type, path, and keyframe count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string", "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string", "description": "Animation name"},
                    "library_name":   {"type": "string", "description": "Library name (optional)"}
                },
                "required": ["animation_name"]
            }
        ),
        Tool(
            name="set_animation_properties",
            description="Set length, loop_mode, and/or step on an existing Animation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string", "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string", "description": "Animation name"},
                    "library_name":   {"type": "string", "description": "Library name (optional)"},
                    "length":         {"type": "number", "description": "New length in seconds"},
                    "loop_mode":      {"type": "string", "description": "none / linear / pingpong"},
                    "step":           {"type": "number", "description": "New step size"}
                },
                "required": ["animation_name"]
            }
        ),
        Tool(
            name="delete_animation",
            description="Remove an animation from an AnimationPlayer's library.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string", "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string", "description": "Animation name to delete"},
                    "library_name":   {"type": "string", "description": "Library name (required if not default library)"}
                },
                "required": ["animation_name"]
            }
        ),
        Tool(
            name="add_animation_track",
            description="Add a new track to an Animation. Track types: value, position_3d, rotation_3d, scale_3d, blend_shape, method, bezier, audio, animation. Returns the new track index.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string", "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string", "description": "Animation name"},
                    "library_name":   {"type": "string", "description": "Library name (optional)"},
                    "track_type":     {"type": "string", "description": "Track type: value/position_3d/rotation_3d/scale_3d/blend_shape/method/bezier/audio/animation"},
                    "track_path":     {"type": "string", "description": "NodePath:property for this track, e.g. 'Skeleton3D:position' or 'MeshInstance3D:blend_shapes/Smile'"},
                    "interpolation":  {"type": "string", "description": "nearest/linear/cubic/linear_angle/cubic_angle (default: linear)"}
                },
                "required": ["animation_name", "track_type", "track_path"]
            }
        ),
        Tool(
            name="remove_animation_track",
            description="Remove a track by index from an Animation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index to remove"}
                },
                "required": ["animation_name", "track_index"]
            }
        ),
        Tool(
            name="set_track_path",
            description="Change the NodePath:property target of an existing animation track.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"},
                    "track_path":     {"type": "string",  "description": "New NodePath:property"}
                },
                "required": ["animation_name", "track_index", "track_path"]
            }
        ),
        Tool(
            name="get_track_info",
            description="Get full info about a specific animation track: type, path, interpolation mode, and all keyframes with time/value/transition.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"}
                },
                "required": ["animation_name", "track_index"]
            }
        ),
        Tool(
            name="set_track_interpolation",
            description="Set the interpolation mode on an animation track. Modes: nearest, linear, cubic, linear_angle, cubic_angle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"},
                    "interpolation":  {"type": "string",  "description": "nearest/linear/cubic/linear_angle/cubic_angle"}
                },
                "required": ["animation_name", "track_index", "interpolation"]
            }
        ),
        Tool(
            name="add_keyframe",
            description="Insert a keyframe at a given time on an animation track. For 3D tracks pass value as [x,y,z] (position/scale) or [x,y,z,w] (rotation quaternion). Returns the new key index.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"},
                    "time":           {"type": "number",  "description": "Time in seconds"},
                    "value":          {"description": "Keyframe value (number, bool, string, or [x,y,z] / [x,y,z,w] array for 3D tracks)"},
                    "transition":     {"type": "number",  "description": "Easing transition (default: 1.0)"}
                },
                "required": ["animation_name", "track_index", "time", "value"]
            }
        ),
        Tool(
            name="remove_keyframe",
            description="Remove a keyframe from an animation track. Specify by key_index, or by time (removes nearest key).",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"},
                    "key_index":      {"type": "integer", "description": "Key index to remove (use this OR time)"},
                    "time":           {"type": "number",  "description": "Remove nearest key at this time (use this OR key_index)"}
                },
                "required": ["animation_name", "track_index"]
            }
        ),
        Tool(
            name="set_keyframe_value",
            description="Update the value of an existing keyframe on an animation track. Arrays are auto-coerced to Vector3/Quaternion based on track type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"},
                    "key_index":      {"type": "integer", "description": "Key index"},
                    "value":          {"description": "New keyframe value"}
                },
                "required": ["animation_name", "track_index", "key_index", "value"]
            }
        ),
        Tool(
            name="set_keyframe_time",
            description="Move an existing keyframe to a new time position on an animation track.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"},
                    "key_index":      {"type": "integer", "description": "Key index"},
                    "time":           {"type": "number",  "description": "New time in seconds"}
                },
                "required": ["animation_name", "track_index", "key_index", "time"]
            }
        ),
        Tool(
            name="get_keyframes",
            description="List all keyframes on an animation track with time, value, and transition. Values are returned as JSON-safe arrays for Vector/Quaternion types.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":    {"type": "string",  "description": "Path to AnimationPlayer"},
                    "animation_name": {"type": "string",  "description": "Animation name"},
                    "library_name":   {"type": "string",  "description": "Library name (optional)"},
                    "track_index":    {"type": "integer", "description": "Track index"}
                },
                "required": ["animation_name", "track_index"]
            }
        ),
        Tool(
            name="setup_animation_tree",
            description="Create an AnimationTree node and wire it to an AnimationPlayer. Sets up a StateMachine or BlendTree root and activates the tree. Essential for 3D character animations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_path":   {"type": "string", "description": "Path to the AnimationPlayer to drive (default: 'AnimationPlayer')"},
                    "parent_path":   {"type": "string", "description": "Parent node path (default: scene root)"},
                    "tree_type":     {"type": "string", "description": "Root node type: state_machine (default) or blend_tree"},
                    "tree_name":     {"type": "string", "description": "Name for the AnimationTree node (default: 'AnimationTree')"}
                }
            }
        ),
        Tool(
            name="add_state_to_machine",
            description="Add an animation state to an AnimationNodeStateMachine. Node types: animation (plays an animation), state_machine (sub-machine), blend_space_1d, blend_space_2d.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tree_path":       {"type": "string", "description": "Path to AnimationTree node"},
                    "state_name":      {"type": "string", "description": "Name for the new state"},
                    "animation_name":  {"type": "string", "description": "Animation to play in this state (for 'animation' node type)"},
                    "node_type":       {"type": "string", "description": "animation / state_machine / blend_space_1d / blend_space_2d (default: animation)"},
                    "position_x":      {"type": "number", "description": "Graph position X"},
                    "position_y":      {"type": "number", "description": "Graph position Y"}
                },
                "required": ["state_name"]
            }
        ),
        Tool(
            name="connect_states",
            description="Add a transition between two states in an AnimationNodeStateMachine. Switch modes: immediate, sync, at_end.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tree_path":    {"type": "string",  "description": "Path to AnimationTree node"},
                    "from_state":   {"type": "string",  "description": "Source state name"},
                    "to_state":     {"type": "string",  "description": "Destination state name"},
                    "switch_mode":  {"type": "string",  "description": "immediate / sync / at_end (default: immediate)"},
                    "auto_advance": {"type": "boolean", "description": "Auto-advance when condition is met (default: false)"}
                },
                "required": ["from_state", "to_state"]
            }
        ),
        Tool(
            name="set_blend_parameter",
            description="Set a parameter on an AnimationTree (e.g. blend position for locomotion blend spaces). Use path like 'parameters/BlendSpace2D/blend_position' with value [x, y].",
            inputSchema={
                "type": "object",
                "properties": {
                    "tree_path":       {"type": "string", "description": "Path to AnimationTree node"},
                    "parameter_path":  {"type": "string", "description": "Full parameter path, e.g. 'parameters/BlendSpace2D/blend_position'"},
                    "value":           {"description": "Parameter value (number, bool, or [x,y] / [x,y,z] array for blend positions)"}
                },
                "required": ["parameter_path", "value"]
            }
        ),
        Tool(
            name="travel_to_state",
            description="Trigger an AnimationNodeStateMachinePlayback.travel() to smoothly transition to a target state. The scene must be playing and AnimationTree must be active.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tree_path":       {"type": "string", "description": "Path to AnimationTree node"},
                    "target_state":    {"type": "string", "description": "Name of the state to travel to"},
                    "playback_param":  {"type": "string", "description": "Parameter path to playback (default: 'parameters/playback')"}
                },
                "required": ["target_state"]
            }
        ),

        # ── Skeleton tools ────────────────────────────────────────────────────
        Tool(
            name="get_skeleton_bones",
            description="List all bones in a Skeleton3D with names, parent indices, rest transforms, current poses, and enabled state. Use to inspect character rigs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the Skeleton3D node"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="set_bone_pose",
            description="Set pose position, rotation, and/or scale on a Skeleton3D bone by name or index. Rotation accepts [x,y,z] Euler degrees or [x,y,z,w] quaternion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":   {"type": "string",  "description": "Path to the Skeleton3D node"},
                    "bone_name":   {"type": "string",  "description": "Bone name (use instead of bone_index)"},
                    "bone_index":  {"type": "integer", "description": "Bone index (use instead of bone_name)"},
                    "position":    {"type": "array",   "description": "[x, y, z] local pose position"},
                    "rotation":    {"type": "array",   "description": "[x,y,z] Euler degrees or [x,y,z,w] quaternion"},
                    "scale":       {"type": "array",   "description": "[x, y, z] pose scale"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="reset_skeleton_pose",
            description="Reset all bone poses in a Skeleton3D to the rest pose, clearing any procedural or manual posing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the Skeleton3D node"}
                },
                "required": ["node_path"]
            }
        ),

        # ── Batch extras ──────────────────────────────────────────────────────
        Tool(
            name="batch_attach_script",
            description="Attach the same GDScript to every node matching a type and/or group filter. Use for giving a class script to all enemies, platforms, collectibles, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path":         {"type": "string",  "description": "res:// path to the .gd script to attach"},
                    "node_type":           {"type": "string",  "description": "Only attach to nodes of this class (e.g. 'CharacterBody3D')"},
                    "group_name":          {"type": "string",  "description": "Only attach to nodes in this group"},
                    "overwrite_existing":  {"type": "boolean", "description": "Overwrite if node already has a script (default: false)"}
                },
                "required": ["script_path"]
            }
        ),
        Tool(
            name="batch_rename_nodes",
            description="Find & replace in node names within a scene subtree. Supports regex. WARNING: may break NodePath references in scripts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search":       {"type": "string",  "description": "String or regex pattern to find in node names"},
                    "replacement":  {"type": "string",  "description": "Replacement string"},
                    "root_path":    {"type": "string",  "description": "Subtree root path (default: scene root)"},
                    "node_type":    {"type": "string",  "description": "Only rename nodes of this class"},
                    "use_regex":    {"type": "boolean", "description": "Treat search as regex (default: false)"}
                },
                "required": ["search", "replacement"]
            }
        ),
        Tool(
            name="move_and_rename_file",
            description="Move and/or rename a file within the project. Both paths must be res:// paths. Triggers filesystem scan so references update.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Current res:// path of the file"},
                    "dest_path":   {"type": "string", "description": "New res:// path (can be a different directory and/or name)"}
                },
                "required": ["source_path", "dest_path"]
            }
        ),
        Tool(
            name="pack_scene",
            description="Save a node (and its children) as a new .tscn PackedScene file. The node stays in the original scene — this creates an independent copy.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":    {"type": "string", "description": "Path to the node to pack"},
                    "output_path":  {"type": "string", "description": "res:// path for the output .tscn file"}
                },
                "required": ["node_path", "output_path"]
            }
        ),
        Tool(
            name="create_resource_file",
            description="Create a .tres resource file of any Godot class (PhysicsMaterial, Environment, Sky, StandardMaterial3D, etc.) and optionally set initial properties.",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_type": {"type": "string", "description": "Godot class name, e.g. PhysicsMaterial, Environment, StandardMaterial3D"},
                    "output_path":   {"type": "string", "description": "res:// path ending in .tres or .res"},
                    "properties":    {"type": "object", "description": "Initial property values to set on the resource"}
                },
                "required": ["output_path"]
            }
        ),

        # ── Project utilities ─────────────────────────────────────────────────
        Tool(
            name="assert_fps_above",
            description="Sample FPS over N frames and assert the average meets a minimum threshold. Requires a scene to be playing for meaningful game FPS measurement.",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold":    {"type": "number",  "description": "Minimum acceptable average FPS (default: 30.0)"},
                    "frame_count":  {"type": "integer", "description": "Number of frames to sample, 1–300 (default: 60)"}
                }
            }
        ),
        Tool(
            name="get_renderer_info",
            description="Get rendering backend, GPU adapter name/vendor, API version, VRAM usage, viewport size, and Godot version.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="assert_resource_valid",
            description="Verify that a res:// resource exists and loads without errors. Returns {passed, resource_type}.",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_path": {"type": "string", "description": "res:// path to the resource to verify"}
                },
                "required": ["resource_path"]
            }
        ),
        Tool(
            name="get_node_global_transform",
            description="Get the world-space position, rotation (degrees), and scale of a Node3D or Node2D.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string", "description": "Path to the Node3D or Node2D"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="set_node_global_transform",
            description="Set the world-space position, rotation (degrees), and/or scale of a Node3D or Node2D.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path":               {"type": "string", "description": "Path to the Node3D or Node2D"},
                    "global_position":         {"type": "array",  "description": "[x,y,z] for Node3D or [x,y] for Node2D"},
                    "global_rotation_degrees": {"type": "array",  "description": "[x,y,z] Euler degrees for Node3D or single float for Node2D"},
                    "global_scale":            {"type": "array",  "description": "[x,y,z] for Node3D or [x,y] for Node2D"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="toggle_feature_tag",
            description="Add or remove a custom feature tag in Project Settings (application/config/features). Tags can be queried at runtime with OS.has_feature('tag_name').",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag":     {"type": "string",  "description": "Feature tag name to add or remove"},
                    "enabled": {"type": "boolean", "description": "True to add the tag, false to remove it (default: true)"}
                },
                "required": ["tag"]
            }
        ),
        Tool(
            name="set_node_metadata",
            description="Set or remove metadata on a node via node.set_meta() / node.remove_meta(). Metadata persists in .tscn files and is accessible at runtime via node.get_meta('key').",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string",  "description": "Path to the target node"},
                    "key":       {"type": "string",  "description": "Metadata key name"},
                    "value":     {"description": "Value to set (any type). Ignored if remove=true."},
                    "remove":    {"type": "boolean", "description": "If true, remove the metadata key instead of setting it (default: false)"}
                },
                "required": ["node_path", "key"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent | ImageContent]:
    """Handle tool calls by proxying to Godot HTTP API"""
    
    # Map tool names to API endpoints
    endpoint_map = {
        # Project tools
        "get_project_info": "/api/project/info",
        "get_filesystem_tree": "/api/project/filesystem",
        "search_files": "/api/project/search_files",
        "uid_to_project_path": "/api/project/uid_to_path",
        "project_path_to_uid": "/api/project/path_to_uid",
        
        # Scene tools
        "get_scene_tree": "/api/scene/tree",
        "get_scene_file_content": "/api/scene/file_content",
        "create_scene": "/api/scene/create",
        "open_scene": "/api/scene/open",
        "delete_scene": "/api/scene/delete",
        "add_scene": "/api/scene/add_scene",
        "play_scene": "/api/scene/play",
        "stop_running_scene": "/api/scene/stop",
        
        # Node tools
        "add_node": "/api/node/add",
        "delete_node": "/api/node/delete",
        "duplicate_node": "/api/node/duplicate",
        "move_node": "/api/node/move",
        "update_property": "/api/node/update_property",
        "add_resource": "/api/node/add_resource",
        "set_anchor_preset": "/api/node/set_anchor_preset",
        "set_anchor_values": "/api/node/set_anchor_values",
        
        # Script tools
        "get_open_scripts": "/api/script/get_open_scripts",
        "view_script": "/api/script/view",
        "create_script": "/api/script/create",
        "attach_script": "/api/script/attach",
        "edit_file": "/api/script/edit_file",
        
        # Editor tools
        "get_godot_errors": "/api/editor/errors",
        "get_editor_screenshot": "/api/editor/screenshot",
        "get_running_scene_screenshot": "/api/editor/running_scene_screenshot",
        "execute_editor_script": "/api/editor/execute_script",
        "clear_output_logs": "/api/editor/clear_logs",
        
        # Windsurf tools
        "get_windsurf_context": "/api/windsurf/context",
        "get_live_preview": "/api/windsurf/live_preview",
        
        # Runtime operations
        "simulate_key_press": "/api/runtime/simulate_key",
        "simulate_action": "/api/runtime/simulate_action",
        "simulate_mouse_button": "/api/runtime/simulate_mouse_button",
        "simulate_mouse_motion": "/api/runtime/simulate_mouse_motion",
        "get_runtime_stats": "/api/runtime/stats",
        "get_node_properties": "/api/runtime/node_properties",
        "get_node_methods": "/api/runtime/node_methods",
        "call_node_method": "/api/runtime/call_method",
        "get_installed_plugins": "/api/runtime/plugins",
        "get_plugin_info": "/api/runtime/plugin_info",
        "get_assets_by_type": "/api/runtime/assets_by_type",
        "get_asset_info": "/api/runtime/asset_info",
        "run_test_script": "/api/runtime/run_test",
        "get_input_actions": "/api/runtime/input_actions",

        # New scene tools
        "save_scene": "/api/scene/save",
        "rename_node": "/api/node/rename",
        "reorder_node": "/api/node/reorder",
        "find_nodes": "/api/node/find",
        "get_node_signals": "/api/node/signals",
        "connect_signal": "/api/node/connect_signal",
        "disconnect_signal": "/api/node/disconnect_signal",
        "add_to_group": "/api/node/add_to_group",
        "remove_from_group": "/api/node/remove_from_group",
        "get_node_groups": "/api/node/get_groups",
        "batch_set_properties": "/api/node/batch_set_properties",
        "get_class_property_list": "/api/node/class_properties",

        # Autoload / project configuration tools
        "get_autoloads": "/api/project/autoloads",
        "add_autoload": "/api/project/autoload_add",
        "remove_autoload": "/api/project/autoload_remove",
        "set_main_scene": "/api/project/set_main_scene",

        # Shader / material tools
        "set_shader_parameter": "/api/node/set_shader_parameter",

        # Resource health tools
        "scan_broken_resources": "/api/project/scan_broken_resources",

        # Import settings tools
        "get_import_settings": "/api/project/import_settings_get",
        "set_import_settings": "/api/project/import_settings_set",

        # Undo / Redo
        "undo": "/api/editor/undo",
        "redo": "/api/editor/redo",

        # Navigation mesh baking
        "bake_navigation_mesh": "/api/scene/bake_navigation",

        # Profiler snapshot
        "get_profiler_snapshot": "/api/runtime/profiler_snapshot",

        # TileMap tools
        "paint_tiles":             "/api/tilemap/paint",
        "fill_tiles_rect":         "/api/tilemap/fill_rect",
        "clear_tiles":             "/api/tilemap/clear",
        "get_cell_tile":           "/api/tilemap/get_cell",

        # GridMap tools
        "set_grid_cell":           "/api/gridmap/set_cell",
        "fill_grid_box":           "/api/gridmap/fill_box",
        "get_grid_used_cells":     "/api/gridmap/used_cells",

        # Batch operation tools
        "batch_set_property_on_type":  "/api/batch/set_property_on_type",
        "batch_set_property_on_group": "/api/batch/set_property_on_group",
        "replace_in_all_scripts":      "/api/batch/replace_in_scripts",
        "batch_create_nodes":          "/api/batch/create_nodes",

        # Animation extras
        "add_blend_space_point":       "/api/animation/blend_space/add_point",
        "get_blend_space_info":        "/api/animation/blend_space/info",
        "copy_animation":              "/api/animation/copy",
        "set_animation_speed_scale":   "/api/animation/set_speed_scale",

        # QA / Validation tools
        "assert_no_errors":        "/api/qa/assert_no_errors",
        "validate_scene":          "/api/qa/validate_scene",
        "simulate_mouse_path":     "/api/qa/simulate_mouse_path",
        "reimport_all":            "/api/qa/reimport_all",
        "set_node_unique_name":    "/api/qa/set_node_unique_name",

        # Audio tools
        "create_audio_player_3d":  "/api/audio/create_3d",
        "play_audio":              "/api/audio/play",
        "stop_audio":              "/api/audio/stop",
        "set_audio_property":      "/api/audio/set_property",
        "get_playback_position":   "/api/audio/playback_position",
        "set_bus_volume":          "/api/audio/set_bus_volume",
        "add_bus_effect":          "/api/audio/add_bus_effect",

        # Testing / QA tools
        "simulate_action_sequence": "/api/test/action_sequence",
        "wait_frames":              "/api/test/wait_frames",
        "assert_node_property":     "/api/test/assert_property",
        "capture_frame_sequence":   "/api/test/frame_sequence",
        "get_scene_statistics":     "/api/test/scene_stats",

        # Editor polish tools
        "select_nodes":                "/api/editor/select_nodes",
        "batch_duplicate_with_offset": "/api/editor/batch_duplicate",
        "find_scripts_with_pattern":   "/api/editor/find_scripts",

        # Physics tools
        "apply_impulse":          "/api/physics/apply_impulse",
        "apply_force":            "/api/physics/apply_force",
        "apply_torque":           "/api/physics/apply_torque",
        "set_linear_velocity":    "/api/physics/set_linear_velocity",
        "set_angular_velocity":   "/api/physics/set_angular_velocity",
        "set_physics_property":   "/api/physics/set_property",
        "create_joint":           "/api/physics/create_joint",

        # Particle tools
        "create_particles":            "/api/particles/create",
        "set_particle_material_param": "/api/particles/set_material_param",
        "restart_particles":           "/api/particles/restart",
        "get_particle_info":           "/api/particles/info",

        # Shader tools
        "create_shader_material": "/api/shader/create_material",
        "get_shader_code":        "/api/shader/get_code",
        "set_shader_code":        "/api/shader/set_code",
        "get_shader_parameters":  "/api/shader/get_parameters",

        # Animation tools
        "get_animation_player_info":  "/api/animation/player_info",
        "create_animation":           "/api/animation/create",
        "get_animation_info":         "/api/animation/info",
        "set_animation_properties":   "/api/animation/set_properties",
        "delete_animation":           "/api/animation/delete",
        "add_animation_track":        "/api/animation/track/add",
        "remove_animation_track":     "/api/animation/track/remove",
        "set_track_path":             "/api/animation/track/set_path",
        "get_track_info":             "/api/animation/track/info",
        "set_track_interpolation":    "/api/animation/track/set_interp",
        "add_keyframe":               "/api/animation/keyframe/add",
        "remove_keyframe":            "/api/animation/keyframe/remove",
        "set_keyframe_value":         "/api/animation/keyframe/set_value",
        "set_keyframe_time":          "/api/animation/keyframe/set_time",
        "get_keyframes":              "/api/animation/keyframe/list",
        "setup_animation_tree":       "/api/animation/tree/setup",
        "add_state_to_machine":       "/api/animation/tree/add_state",
        "connect_states":             "/api/animation/tree/connect_states",
        "set_blend_parameter":        "/api/animation/tree/set_blend",
        "travel_to_state":            "/api/animation/tree/travel",

        # Skeleton tools
        "get_skeleton_bones":          "/api/skeleton/get_bones",
        "set_bone_pose":               "/api/skeleton/set_bone_pose",
        "reset_skeleton_pose":         "/api/skeleton/reset_pose",

        # Batch extras
        "batch_attach_script":         "/api/batch/attach_script",
        "batch_rename_nodes":          "/api/batch/rename_nodes",
        "move_and_rename_file":        "/api/batch/move_file",
        "pack_scene":                  "/api/batch/pack_scene",
        "create_resource_file":        "/api/batch/create_resource",

        # Project utility tools
        "assert_fps_above":            "/api/project/assert_fps",
        "get_renderer_info":           "/api/project/renderer_info",
        "assert_resource_valid":       "/api/project/assert_resource",
        "get_node_global_transform":   "/api/project/node_global_xform",
        "set_node_global_transform":   "/api/project/set_global_xform",
        "toggle_feature_tag":          "/api/project/feature_tag",
        "set_node_metadata":           "/api/project/node_metadata",
    }
    
    # ── Export tools (Python subprocess, no Godot HTTP needed) ───────────────

    if name == "get_export_presets":
        import configparser
        project_path = arguments.get("project_path") or (_godot_project_path if _godot_project_path else os.getcwd())
        presets_path = os.path.join(project_path, "export_presets.cfg")

        if not os.path.exists(presets_path):
            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "presets": [],
                "message": "No export_presets.cfg found. Create presets via Godot: Project → Export → Add preset."
            }, indent=2))]

        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                raw = f.read()

            # Godot cfg files use sections like [preset.0] and [preset.0.options]
            # Standard configparser handles this fine
            cp = configparser.RawConfigParser()
            cp.read_string(raw)

            presets = []
            idx = 0
            while cp.has_section(f"preset.{idx}"):
                sec = f"preset.{idx}"
                opts_sec = f"preset.{idx}.options"
                preset = {
                    "index": idx,
                    "name": cp.get(sec, "name", fallback="").strip('"'),
                    "platform": cp.get(sec, "platform", fallback="").strip('"'),
                    "runnable": cp.get(sec, "runnable", fallback="false") == "true",
                    "export_path": cp.get(sec, "export_path", fallback="").strip('"'),
                    "options": {}
                }
                if cp.has_section(opts_sec):
                    for key, val in cp.items(opts_sec):
                        preset["options"][key] = val.strip('"')
                presets.append(preset)
                idx += 1

            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "count": len(presets),
                "presets": presets
            }, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": f"Failed to parse export_presets.cfg: {e}"
            }, indent=2))]

    if name == "export_project":
        import subprocess
        godot_exe = os.getenv("GODOT_EXECUTABLE")
        if not godot_exe:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": "GODOT_EXECUTABLE environment variable not set. Required for headless export."
            }, indent=2))]

        preset_name = arguments.get("preset_name", "")
        output_path = arguments.get("output_path", "")
        project_path = arguments.get("project_path", os.getcwd())
        debug = arguments.get("debug", False)

        if not preset_name or not output_path:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": "preset_name and output_path are required"
            }, indent=2))]

        export_flag = "--export-debug" if debug else "--export-release"
        cmd = [godot_exe, "--headless", "--path", project_path, export_flag, preset_name, output_path]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            success = proc.returncode == 0
            return [TextContent(type="text", text=json.dumps({
                "success": success,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:] if proc.stdout else "",
                "stderr": proc.stderr[-4000:] if proc.stderr else "",
                "command": " ".join(cmd),
                "note": "Check stderr for Godot export errors. returncode=0 means success."
            }, indent=2))]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": "Export timed out after 5 minutes"
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2))]

    if name == "create_export_preset":
        import configparser
        preset_name = arguments.get("preset_name", "")
        platform     = arguments.get("platform", "")
        export_path  = arguments.get("export_path", "")
        project_path = arguments.get("project_path") or (_godot_project_path if _godot_project_path else os.getcwd())
        runnable     = arguments.get("runnable", True)
        options      = arguments.get("options", {})

        if not preset_name or not platform:
            return [TextContent(type="text", text=json.dumps({
                "success": False, "error": "preset_name and platform are required"
            }, indent=2))]

        presets_path = os.path.join(project_path, "export_presets.cfg")
        cp = configparser.RawConfigParser()
        cp.optionxform = str  # preserve case

        if os.path.exists(presets_path):
            with open(presets_path, "r", encoding="utf-8") as f:
                cp.read_string(f.read())

        # Find next available index; also check for duplicate name
        idx = 0
        while cp.has_section(f"preset.{idx}"):
            existing = cp.get(f"preset.{idx}", "name", fallback="").strip('"')
            if existing == preset_name:
                return [TextContent(type="text", text=json.dumps({
                    "success": False,
                    "error": f"Preset '{preset_name}' already exists at index {idx}"
                }, indent=2))]
            idx += 1

        sec = f"preset.{idx}"
        cp.add_section(sec)
        cp.set(sec, "name",                      f'"{preset_name}"')
        cp.set(sec, "platform",                  f'"{platform}"')
        cp.set(sec, "runnable",                  "true" if runnable else "false")
        cp.set(sec, "dedicated_server",          "false")
        cp.set(sec, "custom_features",           '""')
        cp.set(sec, "export_filter",             '"all_resources"')
        cp.set(sec, "include_filter",            '""')
        cp.set(sec, "exclude_filter",            '""')
        cp.set(sec, "export_path",               f'"{export_path}"')
        cp.set(sec, "encryption_include_filters","\"\"")
        cp.set(sec, "encryption_exclude_filters","\"\"")
        cp.set(sec, "encrypt_pck",               "false")
        cp.set(sec, "encrypt_directory",         "false")

        opts_sec = f"preset.{idx}.options"
        cp.add_section(opts_sec)
        for k, v in options.items():
            cp.set(opts_sec, k, str(v))

        # Write without the [DEFAULT] header configparser adds
        lines = []
        for section in cp.sections():
            lines.append(f"[{section}]\n\n")
            for key, val in cp.items(section):
                lines.append(f"{key}={val}\n")
            lines.append("\n")

        try:
            with open(presets_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "data": {
                    "preset_index": idx,
                    "preset_name": preset_name,
                    "platform": platform,
                    "export_path": export_path,
                    "note": "Preset written. Open Godot to verify and configure export templates."
                }
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "success": False, "error": str(e)
            }, indent=2))]

    # ── Handle Godot process management tools (don't need Godot running) ─────
    if name == "check_godot_running":
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.post(
                    f"{GODOT_BASE_URL}/api/project/info",
                    json={},
                )
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "running": True,
                        "responsive": response.status_code == 200
                    }, indent=2)
                )]
        except Exception:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "running": False,
                    "responsive": False
                }, indent=2)
            )]
    
    if name == "launch_godot":
        import subprocess
        godot_exe = os.getenv("GODOT_EXECUTABLE")
        if not godot_exe:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "GODOT_EXECUTABLE environment variable not set. Please set it to your Godot executable path."
                }, indent=2)
            )]
        
        project_path = arguments.get("project_path")
        editor_mode = arguments.get("editor_mode", True)
        
        try:
            args = [godot_exe]
            if editor_mode:
                args.extend(["--editor", "--path", project_path])
            else:
                args.extend(["--path", project_path])
            
            process = subprocess.Popen(args, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE,
                                     creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": f"Godot launched successfully with PID {process.pid}",
                    "pid": process.pid,
                    "note": "Wait a few seconds for Godot to start and the MCP server to become available"
                }, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Failed to launch Godot: {str(e)}"
                }, indent=2)
            )]
    
    if name == "get_godot_version":
        import subprocess
        godot_exe = os.getenv("GODOT_EXECUTABLE")
        if not godot_exe:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "GODOT_EXECUTABLE environment variable not set"
                }, indent=2)
            )]
        
        try:
            result = subprocess.run([godot_exe, "--version"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            version = result.stdout.strip()
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "version": version,
                    "executable": godot_exe
                }, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Failed to get Godot version: {str(e)}"
                }, indent=2)
            )]
    
    # Handle direct file system tools (prefer Godot when running so editor stays in sync)
    if name in ["read_scene_file", "write_scene_file", "read_script_file", "write_script_file",
                "read_project_settings", "update_project_settings", "create_directory", "list_directory"]:
        
        if name == "read_scene_file":
            scene_path = await resolve_res_path(arguments.get("scene_path", ""))
            
            try:
                with open(scene_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "path": scene_path,
                        "content": content
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to read scene file: {str(e)}"
                    }, indent=2)
                )]
        
        elif name == "write_scene_file":
            raw_path = arguments.get("scene_path", "")
            content = arguments.get("content", "")
            # Prefer Godot-side write so EditorFileSystem scans the change
            if str(raw_path).startswith("res://"):
                res_path = raw_path
            else:
                res_path = await to_res_path(raw_path)

            godot_result = await call_godot_api("/api/file/write_text", {
                "path": res_path if str(res_path).startswith("res://") else raw_path,
                "content": content,
            })
            if godot_result.get("success"):
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "path": godot_result.get("data", {}).get("path", res_path),
                    "message": "Scene file written via Godot (filesystem scanned)",
                    "via": "godot",
                }, indent=2))]

            # Fallback: direct disk write (Godot not running or request failed)
            scene_path = await resolve_res_path(raw_path)
            try:
                os.makedirs(os.path.dirname(scene_path) if os.path.dirname(scene_path) else ".", exist_ok=True)
                with open(scene_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                await notify_godot_filesystem_scan()
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "path": scene_path,
                        "message": "Scene file written to disk",
                        "via": "disk",
                        "godot_error": godot_result.get("error"),
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to write scene file: {str(e)}"
                    }, indent=2)
                )]
        
        elif name == "read_script_file":
            script_path = await resolve_res_path(arguments.get("script_path", ""))
            
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "path": script_path,
                        "content": content
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to read script file: {str(e)}"
                    }, indent=2)
                )]
        
        elif name == "write_script_file":
            raw_path = arguments.get("script_path", "")
            content = arguments.get("content", "")
            if str(raw_path).startswith("res://"):
                res_path = raw_path
            else:
                res_path = await to_res_path(raw_path)

            godot_result = await call_godot_api("/api/file/write_text", {
                "path": res_path if str(res_path).startswith("res://") else raw_path,
                "content": content,
            })
            if godot_result.get("success"):
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "path": godot_result.get("data", {}).get("path", res_path),
                    "message": "Script file written via Godot (filesystem scanned)",
                    "via": "godot",
                }, indent=2))]

            script_path = await resolve_res_path(raw_path)
            try:
                os.makedirs(os.path.dirname(script_path) if os.path.dirname(script_path) else ".", exist_ok=True)
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                await notify_godot_filesystem_scan()
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "path": script_path,
                        "message": "Script file written to disk",
                        "via": "disk",
                        "godot_error": godot_result.get("error"),
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to write script file: {str(e)}"
                    }, indent=2)
                )]
        
        elif name == "read_project_settings":
            project_path = arguments.get("project_path", ".")
            settings_file = os.path.join(project_path, "project.godot")
            
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "path": settings_file,
                        "content": content
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to read project settings: {str(e)}"
                    }, indent=2)
                )]
        
        elif name == "update_project_settings":
            project_path = arguments.get("project_path", ".")
            settings = arguments.get("settings", {}) or {}

            # Prefer Godot ProjectSettings API when the editor is running
            godot_result = await call_godot_api("/api/project/update_settings", {
                "settings": settings,
            })
            if godot_result.get("success"):
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "message": "Project settings updated via Godot ProjectSettings.save()",
                    "via": "godot",
                    "data": godot_result.get("data", {}),
                }, indent=2))]

            # Offline fallback: section-aware project.godot edit
            settings_file = os.path.join(project_path, "project.godot")
            try:
                updated = _update_project_godot_file(settings_file, settings)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "message": "Project settings updated on disk (section-aware)",
                        "via": "disk",
                        "updated": updated,
                        "godot_error": godot_result.get("error"),
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to update project settings: {str(e)}"
                    }, indent=2)
                )]
        
        elif name == "create_directory":
            dir_path = arguments.get("dir_path", "")

            # Prefer Godot so the filesystem dock refreshes
            godot_path = dir_path
            if not str(dir_path).startswith("res://"):
                godot_path = await to_res_path(dir_path)
            godot_result = await call_godot_api("/api/file/create_directory", {
                "dir_path": godot_path if str(godot_path).startswith("res://") else dir_path,
            })
            if godot_result.get("success"):
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "path": godot_result.get("data", {}).get("path", godot_path),
                    "message": "Directory created via Godot (filesystem scanned)",
                    "via": "godot",
                }, indent=2))]

            disk_path = dir_path
            if str(disk_path).startswith("res://"):
                disk_path = await resolve_res_path(disk_path)
            try:
                os.makedirs(disk_path, exist_ok=True)
                await notify_godot_filesystem_scan()
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "path": disk_path,
                        "message": "Directory created on disk",
                        "via": "disk",
                        "godot_error": godot_result.get("error"),
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to create directory: {str(e)}"
                    }, indent=2)
                )]
        
        elif name == "list_directory":
            dir_path = arguments.get("dir_path", ".")
            recursive = arguments.get("recursive", False)
            
            if dir_path.startswith("res://"):
                dir_path = await resolve_res_path(dir_path)
            
            try:
                if recursive:
                    files = []
                    for root, dirs, filenames in os.walk(dir_path):
                        for filename in filenames:
                            files.append(os.path.join(root, filename))
                else:
                    files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)]
                
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "path": dir_path,
                        "files": files,
                        "count": len(files)
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Failed to list directory: {str(e)}"
                    }, indent=2)
                )]
    
    if name not in endpoint_map:
        return [TextContent(
            type="text",
            text=json.dumps({"success": False, "error": f"Unknown tool: {name}"}, indent=2)
        )]
    
    endpoint = endpoint_map[name]
    result = await call_godot_api(endpoint, arguments or {})
    
    # Handle screenshot results (return as image)
    if name in ["get_editor_screenshot", "get_running_scene_screenshot"]:
        if result.get("success") and "data" in result:
            screenshot_base64 = result["data"].get("screenshot", "")
            if screenshot_base64:
                return [
                    TextContent(type="text", text=f"Screenshot captured successfully"),
                    ImageContent(
                        type="image",
                        data=screenshot_base64,
                        mimeType="image/png"
                    )
                ]
    
    # Handle live preview with image
    if name == "get_live_preview":
        if result.get("success") and "data" in result:
            data = result["data"]
            screenshot = data.get("screenshot", "")
            
            response = [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "scene_tree": data.get("scene_tree"),
                        "current_script": data.get("current_script")
                    }, indent=2)
                )
            ]
            
            if screenshot:
                response.append(ImageContent(
                    type="image",
                    data=screenshot,
                    mimeType="image/png"
                ))
            
            return response
    
    # Default: return JSON result
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]

def main_entry():
    """Synchronous entry point for console script"""
    asyncio.run(main())


async def main():
    """Main entry point for the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    main_entry()  # Changed this too