@tool
extends Node

var editor_interface: EditorInterface

signal file_system_changed()


func get_filesystem_tree(path: String = "res://", filters: Array = []) -> Dictionary:
	"""Get recursive tree view of project filesystem"""
	var tree = _build_directory_tree(path, filters)
	return tree


func _build_directory_tree(path: String, filters: Array, depth: int = 0, max_depth: int = 10) -> Dictionary:
	"""Recursively build directory tree"""
	if depth > max_depth:
		return {"name": "...", "type": "truncated"}
	
	var dir = DirAccess.open(path)
	if not dir:
		return {"error": "Cannot open directory: " + path}
	
	var tree = {
		"name": path.get_file() if path != "res://" else "Project Root",
		"path": path,
		"type": "directory",
		"children": []
	}
	
	# List files and directories
	var items = []
	dir.list_dir_begin()
	var item_name = dir.get_next()
	
	while item_name != "":
		# Skip hidden files and .godot directory
		if not item_name.begins_with("."):
			var item_path = path.path_join(item_name)
			var is_dir = dir.current_is_dir()
			
			# Apply filters
			if filters.size() > 0 and not is_dir:
				var passes_filter = false
				for filter in filters:
					if item_name.ends_with(filter):
						passes_filter = true
						break
				if not passes_filter:
					item_name = dir.get_next()
					continue
			
			if is_dir:
				items.append({
					"name": item_name,
					"path": item_path,
					"type": "directory",
					"is_dir": true
				})
			else:
				items.append({
					"name": item_name,
					"path": item_path,
					"type": _get_file_type(item_name),
					"size": _get_file_size(item_path),
					"is_dir": false
				})
		
		item_name = dir.get_next()
	
	dir.list_dir_end()
	
	# Sort: directories first, then files
	items.sort_custom(func(a, b): 
		if a.is_dir and not b.is_dir:
			return true
		elif not a.is_dir and b.is_dir:
			return false
		else:
			return a.name < b.name
	)
	
	# Build children
	for item in items:
		if item.is_dir:
			tree["children"].append(_build_directory_tree(item.path, filters, depth + 1, max_depth))
		else:
			tree["children"].append({
				"name": item.name,
				"path": item.path,
				"type": item.type,
				"size": item.size
			})
	
	return tree


func get_quick_project_overview() -> Dictionary:
	"""Get quick overview of project structure (Windsurf feature)"""
	var overview = {
		"total_scenes": 0,
		"total_scripts": 0,
		"total_assets": 0,
		"directories": []
	}
	
	_count_project_files("res://", overview)
	
	return overview


func _count_project_files(path: String, counts: Dictionary) -> void:
	"""Recursively count project files"""
	var dir = DirAccess.open(path)
	if not dir:
		return
	
	dir.list_dir_begin()
	var item_name = dir.get_next()
	
	while item_name != "":
		if not item_name.begins_with("."):
			var item_path = path.path_join(item_name)
			
			if dir.current_is_dir():
				counts["directories"].append(item_name)
				_count_project_files(item_path, counts)
			else:
				if item_name.ends_with(".tscn") or item_name.ends_with(".scn"):
					counts["total_scenes"] += 1
				elif item_name.ends_with(".gd") or item_name.ends_with(".cs"):
					counts["total_scripts"] += 1
				else:
					counts["total_assets"] += 1
		
		item_name = dir.get_next()
	
	dir.list_dir_end()


func search_files(query: String, search_path: String = "res://") -> Array:
	"""Fuzzy search for files matching query"""
	var results = []
	_search_files_recursive(search_path, query.to_lower(), results)
	
	# Sort by relevance (exact matches first, then contains)
	results.sort_custom(func(a, b):
		var a_name = a.name.to_lower()
		var b_name = b.name.to_lower()
		var query_lower = query.to_lower()
		
		var a_exact = a_name == query_lower
		var b_exact = b_name == query_lower
		
		if a_exact and not b_exact:
			return true
		elif b_exact and not a_exact:
			return false
		
		var a_starts = a_name.begins_with(query_lower)
		var b_starts = b_name.begins_with(query_lower)
		
		if a_starts and not b_starts:
			return true
		elif b_starts and not a_starts:
			return false
		
		return a_name < b_name
	)
	
	return results


func _search_files_recursive(path: String, query: String, results: Array, max_results: int = 50) -> void:
	"""Recursively search files"""
	if results.size() >= max_results:
		return
	
	var dir = DirAccess.open(path)
	if not dir:
		return
	
	dir.list_dir_begin()
	var item_name = dir.get_next()
	
	while item_name != "" and results.size() < max_results:
		if not item_name.begins_with("."):
			var item_path = path.path_join(item_name)
			
			if dir.current_is_dir():
				_search_files_recursive(item_path, query, results, max_results)
			else:
				# Fuzzy match
				if _fuzzy_match(item_name.to_lower(), query):
					results.append({
						"name": item_name,
						"path": item_path,
						"type": _get_file_type(item_name),
						"directory": path
					})
		
		item_name = dir.get_next()
	
	dir.list_dir_end()


func _fuzzy_match(text: String, pattern: String) -> bool:
	"""Simple fuzzy matching"""
	if pattern in text:
		return true
	
	# Check if pattern characters appear in order
	var pattern_idx = 0
	for i in range(text.length()):
		if pattern_idx < pattern.length() and text[i] == pattern[pattern_idx]:
			pattern_idx += 1
	
	return pattern_idx == pattern.length()


func _get_file_type(filename: String) -> String:
	"""Get file type from extension"""
	var ext = filename.get_extension().to_lower()
	
	match ext:
		"tscn", "scn": return "scene"
		"gd": return "gdscript"
		"cs": return "csharp"
		"tres", "res": return "resource"
		"png", "jpg", "jpeg", "webp", "svg": return "texture"
		"wav", "ogg", "mp3": return "audio"
		"glb", "gltf", "obj", "fbx": return "3d_model"
		"gdshader", "shader": return "shader"
		"txt", "md", "json", "cfg": return "text"
		_: return "file"


func uid_to_project_path(uid: String) -> String:
	"""Convert Godot UID to project path"""
	if not uid.begins_with("uid://"):
		return ""
	
	# Use ResourceLoader to convert UID to path
	var path = ResourceUID.get_id_path(ResourceUID.text_to_id(uid))
	return path


func project_path_to_uid(path: String) -> String:
	"""Convert project path to Godot UID"""
	if not path.begins_with("res://"):
		path = "res://" + path
	
	if not FileAccess.file_exists(path):
		return ""
	
	# Get UID for the resource
	var uid_int = ResourceLoader.get_resource_uid(path)
	if uid_int == ResourceUID.INVALID_ID:
		return ""
	
	return ResourceUID.id_to_text(uid_int)


func get_file_content(file_path: String) -> Dictionary:
	"""Get content of a file"""
	if not file_path.begins_with("res://"):
		file_path = "res://" + file_path
	
	if not FileAccess.file_exists(file_path):
		return {"success": false, "error": "File not found: " + file_path}
	
	var file = FileAccess.open(file_path, FileAccess.READ)
	if not file:
		return {"success": false, "error": "Failed to open file: " + file_path}
	
	var content = file.get_as_text()
	file.close()
	
	return {"success": true, "data": {"path": file_path, "content": content}}


func create_directory(dir_path: String) -> Dictionary:
	"""Create a directory"""
	if not dir_path.begins_with("res://"):
		dir_path = "res://" + dir_path
	
	var dir = DirAccess.open("res://")
	if dir.dir_exists(dir_path):
		return {"success": false, "error": "Directory already exists: " + dir_path}
	
	var error = dir.make_dir_recursive(dir_path)
	if error != OK:
		return {"success": false, "error": "Failed to create directory: " + error_string(error)}

	if editor_interface:
		editor_interface.get_resource_filesystem().scan()

	emit_signal("file_system_changed")
	return {"success": true, "data": {"path": dir_path}}


func delete_file(file_path: String) -> Dictionary:
	"""Delete a file"""
	if not file_path.begins_with("res://"):
		file_path = "res://" + file_path
	
	if not FileAccess.file_exists(file_path):
		return {"success": false, "error": "File not found: " + file_path}
	
	var dir = DirAccess.open("res://")
	var error = dir.remove(file_path)
	
	if error != OK:
		return {"success": false, "error": "Failed to delete file: " + error_string(error)}
	
	emit_signal("file_system_changed")
	return {"success": true, "data": {"path": file_path}}


func rename_file(old_path: String, new_path: String) -> Dictionary:
	"""Rename or move a file"""
	if not old_path.begins_with("res://"):
		old_path = "res://" + old_path
	if not new_path.begins_with("res://"):
		new_path = "res://" + new_path
	
	if not FileAccess.file_exists(old_path):
		return {"success": false, "error": "File not found: " + old_path}
	
	var dir = DirAccess.open("res://")
	var error = dir.rename(old_path, new_path)
	
	if error != OK:
		return {"success": false, "error": "Failed to rename file: " + error_string(error)}
	
	emit_signal("file_system_changed")
	return {"success": true, "data": {"old_path": old_path, "new_path": new_path}}


func get_recent_files(count: int = 10) -> Array:
	"""Get recently modified files (Windsurf feature)"""
	var files = []
	_get_all_files("res://", files)
	
	# Sort by modification time
	files.sort_custom(func(a, b):
		return a.modified > b.modified
	)
	
	if files.size() > count:
		files.resize(count)
	
	return files


func _get_all_files(path: String, results: Array) -> void:
	"""Get all files recursively with metadata"""
	var dir = DirAccess.open(path)
	if not dir:
		return
	
	dir.list_dir_begin()
	var item_name = dir.get_next()
	
	while item_name != "":
		if not item_name.begins_with("."):
			var item_path = path.path_join(item_name)
			
			if dir.current_is_dir():
				_get_all_files(item_path, results)
			else:
				results.append({
					"name": item_name,
					"path": item_path,
					"type": _get_file_type(item_name),
					"modified": FileAccess.get_modified_time(item_path)
				})
		
		item_name = dir.get_next()
	
	dir.list_dir_end()


func analyze_project_dependencies() -> Dictionary:
	"""Analyze project dependencies (Windsurf feature for understanding codebase)"""
	var dependencies = {
		"scenes": {},
		"scripts": {},
		"resources": {}
	}
	
	# Scan all scene files for dependencies
	var scenes = []
	_find_files_by_extension("res://", ".tscn", scenes)
	
	for scene_path in scenes:
		var deps = _get_file_dependencies(scene_path)
		dependencies["scenes"][scene_path] = deps
	
	return {"success": true, "data": dependencies}


func _find_files_by_extension(path: String, extension: String, results: Array) -> void:
	"""Find all files with specific extension"""
	var dir = DirAccess.open(path)
	if not dir:
		return
	
	dir.list_dir_begin()
	var item_name = dir.get_next()
	
	while item_name != "":
		if not item_name.begins_with("."):
			var item_path = path.path_join(item_name)
			
			if dir.current_is_dir():
				_find_files_by_extension(item_path, extension, results)
			elif item_name.ends_with(extension):
				results.append(item_path)
		
		item_name = dir.get_next()
	
	dir.list_dir_end()


func _get_file_dependencies(file_path: String) -> Array:
	"""Get dependencies of a file"""
	var deps = []
	var file = FileAccess.open(file_path, FileAccess.READ)
	
	if not file:
		return deps
	
	var content = file.get_as_text()
	file.close()
	
	# Simple regex-based dependency detection
	# Look for res:// paths and uid:// references
	var regex_res = RegEx.new()
	regex_res.compile("res://[^\"\\s]+")
	
	var matches = regex_res.search_all(content)
	for match_obj in matches:
		var dep_path = match_obj.get_string()
		if not dep_path in deps:
			deps.append(dep_path)
	
	return deps


func get_installed_plugins() -> Dictionary:
	"""Get list of all installed plugins with their information"""
	var plugins = []
	var addons_path = "res://addons/"
	
	var dir = DirAccess.open(addons_path)
	if not dir:
		return {"success": false, "error": "Cannot access addons directory"}
	
	dir.list_dir_begin()
	var plugin_dir = dir.get_next()
	
	while plugin_dir != "":
		if dir.current_is_dir() and not plugin_dir.begins_with("."):
			var plugin_cfg_path = addons_path.path_join(plugin_dir).path_join("plugin.cfg")
			
			if FileAccess.file_exists(plugin_cfg_path):
				var plugin_info = _parse_plugin_cfg(plugin_cfg_path, plugin_dir)
				if plugin_info:
					plugins.append(plugin_info)
		
		plugin_dir = dir.get_next()
	
	dir.list_dir_end()
	
	return {"success": true, "data": {"plugins": plugins, "count": plugins.size()}}


func _parse_plugin_cfg(cfg_path: String, plugin_dir: String) -> Dictionary:
	"""Parse plugin.cfg file and extract information"""
	var config = ConfigFile.new()
	var err = config.load(cfg_path)
	
	if err != OK:
		return {}
	
	var plugin_info = {
		"directory": plugin_dir,
		"path": "res://addons/" + plugin_dir,
		"name": config.get_value("plugin", "name", plugin_dir),
		"description": config.get_value("plugin", "description", ""),
		"author": config.get_value("plugin", "author", ""),
		"version": config.get_value("plugin", "version", ""),
		"script": config.get_value("plugin", "script", ""),
		"enabled": EditorInterface.is_plugin_enabled(plugin_dir) if EditorInterface else false
	}

	return plugin_info


func _get_file_size(path: String) -> int:
	"""Return file size in bytes without loading the entire file into memory."""
	var f = FileAccess.open(path, FileAccess.READ)
	if not f:
		return 0
	var size = f.get_length()
	f.close()
	return size


func write_text_file(file_path: String, content: String) -> Dictionary:
	"""Write text content to a project file and trigger a filesystem scan so the
	editor sees the change. Prefer this over writing from the Python process."""
	if not file_path.begins_with("res://"):
		file_path = "res://" + file_path

	# Ensure parent directory exists
	var dir_path = file_path.get_base_dir()
	if dir_path != "" and dir_path != "res://":
		var dir = DirAccess.open("res://")
		if dir and not dir.dir_exists(dir_path):
			var mk_err = dir.make_dir_recursive(dir_path)
			if mk_err != OK:
				return {"success": false, "error": "Failed to create directory: " + error_string(mk_err)}

	var file = FileAccess.open(file_path, FileAccess.WRITE)
	if not file:
		return {"success": false, "error": "Failed to write file: " + file_path + " (" + error_string(FileAccess.get_open_error()) + ")"}

	file.store_string(content)
	file.close()

	if editor_interface:
		editor_interface.get_resource_filesystem().scan()

	emit_signal("file_system_changed")
	print("[File Operations] Wrote text file: ", file_path, " (", content.length(), " chars)")
	return {"success": true, "data": {"path": file_path, "bytes": content.length()}}


func update_project_settings_values(settings: Dictionary) -> Dictionary:
	"""Update ProjectSettings keys and persist via ProjectSettings.save().
	Keys use Godot ProjectSettings paths (e.g. application/config/name)."""
	if settings.is_empty():
		return {"success": false, "error": "No settings provided"}

	var updated: Array = []
	for key in settings.keys():
		var key_str = str(key)
		ProjectSettings.set_setting(key_str, settings[key])
		updated.append(key_str)

	var err = ProjectSettings.save()
	if err != OK:
		return {"success": false, "error": "ProjectSettings.save() failed: " + error_string(err)}

	print("[File Operations] Updated project settings: ", updated)
	return {"success": true, "data": {"updated": updated}}


# ── Import Settings ──────────────────────────────────────────────────────────

func get_import_settings(resource_path: String) -> Dictionary:
	"""Read the .import file for a resource and return all sections/keys"""
	if not resource_path.begins_with("res://"):
		resource_path = "res://" + resource_path

	var import_path = resource_path + ".import"
	if not FileAccess.file_exists(import_path):
		return {"success": false, "error": "No .import file for: %s (only imported assets have one)" % resource_path}

	var cfg = ConfigFile.new()
	var err = cfg.load(import_path)
	if err != OK:
		return {"success": false, "error": "Failed to read .import file: " + error_string(err)}

	var data = {}
	for section in cfg.get_sections():
		data[section] = {}
		for key in cfg.get_section_keys(section):
			data[section][key] = cfg.get_value(section, key)

	return {
		"success": true,
		"data": {
			"resource_path": resource_path,
			"import_file": import_path,
			"settings": data,
			"hint": "Edit keys under 'params' section, then call set_import_settings to apply."
		}
	}


func set_import_settings(resource_path: String, params: Dictionary) -> Dictionary:
	"""Write new values into the [params] section of a .import file and trigger reimport"""
	if not resource_path.begins_with("res://"):
		resource_path = "res://" + resource_path

	var import_path = resource_path + ".import"
	if not FileAccess.file_exists(import_path):
		return {"success": false, "error": "No .import file for: " + resource_path}

	var cfg = ConfigFile.new()
	var err = cfg.load(import_path)
	if err != OK:
		return {"success": false, "error": "Failed to read .import file: " + error_string(err)}

	# Apply each setting into the [params] section
	for key in params:
		cfg.set_value("params", key, params[key])

	err = cfg.save(import_path)
	if err != OK:
		return {"success": false, "error": "Failed to save .import file: " + error_string(err)}

	# Trigger Godot to reimport the asset
	if editor_interface:
		editor_interface.get_resource_filesystem().reimport_files([resource_path])
	else:
		push_warning("[File Operations] editor_interface not set — skipping reimport trigger")

	print("[File Operations] Import settings updated and reimport triggered: ", resource_path)
	return {
		"success": true,
		"data": {
			"resource_path": resource_path,
			"updated_params": params,
			"message": "Reimport triggered. Asset will be re-processed by Godot."
		}
	}
