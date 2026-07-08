@tool
extends EditorPlugin

const HTTPServer = preload("res://addons/godot_mcp_enhanced/http_server.gd")
const ScreenshotManager = preload("res://addons/godot_mcp_enhanced/screenshot_manager.gd")
const SceneOperations = preload("res://addons/godot_mcp_enhanced/scene_operations.gd")
const ScriptOperations = preload("res://addons/godot_mcp_enhanced/script_operations.gd")
const DebuggerIntegration = preload("res://addons/godot_mcp_enhanced/debugger_integration.gd")
const FileOperations = preload("res://addons/godot_mcp_enhanced/file_operations.gd")
const RuntimeOperations = preload("res://addons/godot_mcp_enhanced/runtime_operations.gd")
const AnimationOperations = preload("res://addons/godot_mcp_enhanced/animation_operations.gd")
const PhysicsOperations = preload("res://addons/godot_mcp_enhanced/physics_operations.gd")
const ParticlesOperations = preload("res://addons/godot_mcp_enhanced/particles_operations.gd")
const ShaderOperations = preload("res://addons/godot_mcp_enhanced/shader_operations.gd")
const AudioOperations = preload("res://addons/godot_mcp_enhanced/audio_operations.gd")
const TestingOperations = preload("res://addons/godot_mcp_enhanced/testing_operations.gd")
const EditorPolishOperations = preload("res://addons/godot_mcp_enhanced/editor_polish_operations.gd")
const TilemapOperations = preload("res://addons/godot_mcp_enhanced/tilemap_operations.gd")
const BatchOperations = preload("res://addons/godot_mcp_enhanced/batch_operations.gd")
const AnimationExtras = preload("res://addons/godot_mcp_enhanced/animation_extras.gd")
const QAValidationOperations = preload("res://addons/godot_mcp_enhanced/qa_validation_operations.gd")
const SkeletonOperations = preload("res://addons/godot_mcp_enhanced/skeleton_operations.gd")
const BatchExtras = preload("res://addons/godot_mcp_enhanced/batch_extras.gd")
const ProjectUtils = preload("res://addons/godot_mcp_enhanced/project_utils.gd")

var http_server: Node
var screenshot_manager: Node
var scene_operations: Node
var script_operations: Node
var debugger_integration: Node
var file_operations: Node
var runtime_operations: Node
var animation_operations: Node
var physics_operations: Node
var particles_operations: Node
var shader_operations: Node
var audio_operations: Node
var testing_operations: Node
var editor_polish_operations: Node
var tilemap_operations: Node
var batch_operations: Node
var animation_extras: Node
var qa_validation_operations: Node
var skeleton_operations: Node
var batch_extras: Node
var project_utils: Node

var bottom_panel: Control
var config: Dictionary = {}
var config_path: String = "res://godot_mcp_config.json"


func _enter_tree() -> void:
	print("[Godot MCP Enhanced] Initializing plugin...")
	
	# Load configuration
	_load_config()
	
	# Initialize core systems
	http_server = HTTPServer.new()
	http_server.name = "MCPHTTPServer"
	add_child(http_server)
	
	screenshot_manager = ScreenshotManager.new()
	screenshot_manager.name = "MCPScreenshotManager"
	add_child(screenshot_manager)
	
	scene_operations = SceneOperations.new()
	scene_operations.name = "MCPSceneOperations"
	scene_operations.editor_interface = get_editor_interface()
	add_child(scene_operations)
	
	script_operations = ScriptOperations.new()
	script_operations.name = "MCPScriptOperations"
	script_operations.editor_interface = get_editor_interface()
	add_child(script_operations)
	
	debugger_integration = DebuggerIntegration.new()
	debugger_integration.name = "MCPDebuggerIntegration"
	debugger_integration.editor_interface = get_editor_interface()
	add_child(debugger_integration)
	
	file_operations = FileOperations.new()
	file_operations.name = "MCPFileOperations"
	file_operations.editor_interface = get_editor_interface()
	add_child(file_operations)
	
	runtime_operations = RuntimeOperations.new()
	runtime_operations.name = "MCPRuntimeOperations"
	runtime_operations.editor_interface = get_editor_interface()
	add_child(runtime_operations)

	animation_operations = AnimationOperations.new()
	animation_operations.name = "MCPAnimationOperations"
	animation_operations.editor_interface = get_editor_interface()
	add_child(animation_operations)

	physics_operations = PhysicsOperations.new()
	physics_operations.name = "MCPPhysicsOperations"
	physics_operations.editor_interface = get_editor_interface()
	add_child(physics_operations)

	particles_operations = ParticlesOperations.new()
	particles_operations.name = "MCPParticlesOperations"
	particles_operations.editor_interface = get_editor_interface()
	add_child(particles_operations)

	shader_operations = ShaderOperations.new()
	shader_operations.name = "MCPShaderOperations"
	shader_operations.editor_interface = get_editor_interface()
	add_child(shader_operations)

	audio_operations = AudioOperations.new()
	audio_operations.name = "MCPAudioOperations"
	audio_operations.editor_interface = get_editor_interface()
	add_child(audio_operations)

	testing_operations = TestingOperations.new()
	testing_operations.name = "MCPTestingOperations"
	testing_operations.editor_interface = get_editor_interface()
	add_child(testing_operations)

	editor_polish_operations = EditorPolishOperations.new()
	editor_polish_operations.name = "MCPEditorPolishOperations"
	editor_polish_operations.editor_interface = get_editor_interface()
	add_child(editor_polish_operations)

	tilemap_operations = TilemapOperations.new()
	tilemap_operations.name = "MCPTilemapOperations"
	tilemap_operations.editor_interface = get_editor_interface()
	add_child(tilemap_operations)

	batch_operations = BatchOperations.new()
	batch_operations.name = "MCPBatchOperations"
	batch_operations.editor_interface = get_editor_interface()
	add_child(batch_operations)

	animation_extras = AnimationExtras.new()
	animation_extras.name = "MCPAnimationExtras"
	animation_extras.editor_interface = get_editor_interface()
	add_child(animation_extras)

	qa_validation_operations = QAValidationOperations.new()
	qa_validation_operations.name = "MCPQAValidationOperations"
	qa_validation_operations.editor_interface = get_editor_interface()
	qa_validation_operations.debugger_ref = debugger_integration  # pass error log reference
	add_child(qa_validation_operations)

	skeleton_operations = SkeletonOperations.new()
	skeleton_operations.name = "MCPSkeletonOperations"
	skeleton_operations.editor_interface = get_editor_interface()
	add_child(skeleton_operations)

	batch_extras = BatchExtras.new()
	batch_extras.name = "MCPBatchExtras"
	batch_extras.editor_interface = get_editor_interface()
	add_child(batch_extras)

	project_utils = ProjectUtils.new()
	project_utils.name = "MCPProjectUtils"
	project_utils.editor_interface = get_editor_interface()
	add_child(project_utils)

	# Connect HTTP server to operation handlers
	_setup_http_routes()
	
	# Create bottom panel UI
	_create_bottom_panel()
	
	# Start HTTP server
	var port = int(config.get("GDAI_MCP_SERVER_PORT", 3571))
	print("[Godot MCP Enhanced] Attempting to start HTTP server on port %d..." % port)
	
	var success = http_server.start_server(port)
	
	if success:
		print("[Godot MCP Enhanced] ✓ HTTP Server started successfully on port %d" % port)
		# Update UI status
		if bottom_panel:
			bottom_panel.update_server_status(true)
	else:
		push_error("[Godot MCP Enhanced] ✗ Failed to start HTTP server on port %d!" % port)
		push_error("[Godot MCP Enhanced] Port may already be in use or blocked by firewall")
		push_error("[Godot MCP Enhanced] Try changing GDAI_MCP_SERVER_PORT in godot_mcp_config.json")
		# Update UI status
		if bottom_panel:
			bottom_panel.update_server_status(false)
	
	print("[Godot MCP Enhanced] Plugin initialization complete")


func _exit_tree() -> void:
	print("[Godot MCP Enhanced] Shutting down plugin...")
	
	# Stop HTTP server
	if http_server:
		http_server.stop_server()
	
	# Remove bottom panel
	if bottom_panel:
		remove_control_from_bottom_panel(bottom_panel)
		bottom_panel.queue_free()
	
	# Clean up nodes
	for child in [http_server, screenshot_manager, scene_operations,
				  script_operations, debugger_integration, file_operations,
				  runtime_operations, animation_operations,
				  physics_operations, particles_operations, shader_operations,
				  audio_operations, testing_operations, editor_polish_operations,
				  tilemap_operations, batch_operations, animation_extras,
				  qa_validation_operations,
				  skeleton_operations, batch_extras, project_utils]:
		if child:
			child.queue_free()
	
	print("[Godot MCP Enhanced] Plugin shutdown complete")


func _load_config() -> void:
	if FileAccess.file_exists(config_path):
		var file = FileAccess.open(config_path, FileAccess.READ)
		if file:
			var json_text = file.get_as_text()
			file.close()
			
			var json = JSON.new()
			var error = json.parse(json_text)
			if error == OK:
				config = json.get_data()
				print("[Godot MCP Enhanced] Configuration loaded from ", config_path)
			else:
				push_error("[Godot MCP Enhanced] Failed to parse config: " + json.get_error_message())
	else:
		# Create default config
		config = {
			"GDAI_MCP_SERVER_PORT": "3571",
			"GDAI_RUNTIME_SERVER_PORT": "3572",
			"AUTO_SCREENSHOT": true,
			"SCREENSHOT_ON_SCENE_CHANGE": true,
			"SCREENSHOT_ON_ERROR": true
		}
		_save_config()


func _save_config() -> void:
	var file = FileAccess.open(config_path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(config, "\t"))
		file.close()
		print("[Godot MCP Enhanced] Configuration saved to ", config_path)


func _setup_http_routes() -> void:
	# Project tools
	http_server.register_route("/api/project/info", _handle_get_project_info)
	http_server.register_route("/api/project/filesystem", _handle_get_filesystem_tree)
	http_server.register_route("/api/project/search_files", _handle_search_files)
	http_server.register_route("/api/project/uid_to_path", _handle_uid_to_project_path)
	http_server.register_route("/api/project/path_to_uid", _handle_project_path_to_uid)
	http_server.register_route("/api/project/update_settings", _handle_update_project_settings)
	http_server.register_route("/api/file/write_text", _handle_write_text_file)
	http_server.register_route("/api/file/create_directory", _handle_create_directory)
	
	# Scene tools
	http_server.register_route("/api/scene/tree", _handle_get_scene_tree)
	http_server.register_route("/api/scene/file_content", _handle_get_scene_file_content)
	http_server.register_route("/api/scene/create", _handle_create_scene)
	http_server.register_route("/api/scene/open", _handle_open_scene)
	http_server.register_route("/api/scene/delete", _handle_delete_scene)
	http_server.register_route("/api/scene/add_scene", _handle_add_scene)
	http_server.register_route("/api/scene/play", _handle_play_scene)
	http_server.register_route("/api/scene/stop", _handle_stop_running_scene)
	
	# Node tools
	http_server.register_route("/api/node/add", _handle_add_node)
	http_server.register_route("/api/node/delete", _handle_delete_node)
	http_server.register_route("/api/node/duplicate", _handle_duplicate_node)
	http_server.register_route("/api/node/move", _handle_move_node)
	http_server.register_route("/api/node/update_property", _handle_update_property)
	http_server.register_route("/api/node/add_resource", _handle_add_resource)
	http_server.register_route("/api/node/set_anchor_preset", _handle_set_anchor_preset)
	http_server.register_route("/api/node/set_anchor_values", _handle_set_anchor_values)
	
	# Script tools
	http_server.register_route("/api/script/get_open_scripts", _handle_get_open_scripts)
	http_server.register_route("/api/script/view", _handle_view_script)
	http_server.register_route("/api/script/create", _handle_create_script)
	http_server.register_route("/api/script/attach", _handle_attach_script)
	http_server.register_route("/api/script/edit_file", _handle_edit_file)
	
	# Editor tools
	http_server.register_route("/api/editor/errors", _handle_get_godot_errors)
	http_server.register_route("/api/editor/screenshot", _handle_get_editor_screenshot)
	http_server.register_route("/api/editor/running_scene_screenshot", _handle_get_running_scene_screenshot)
	http_server.register_route("/api/editor/execute_script", _handle_execute_editor_script)
	http_server.register_route("/api/editor/clear_logs", _handle_clear_output_logs)
	
	# Windsurf-specific tools
	http_server.register_route("/api/windsurf/context", _handle_get_windsurf_context)
	http_server.register_route("/api/windsurf/live_preview", _handle_get_live_preview)

	# Autoload tools
	http_server.register_route("/api/project/autoloads", _handle_get_autoloads)
	http_server.register_route("/api/project/autoload_add", _handle_add_autoload)
	http_server.register_route("/api/project/autoload_remove", _handle_remove_autoload)
	http_server.register_route("/api/project/set_main_scene", _handle_set_main_scene)
	http_server.register_route("/api/project/scan_broken_resources", _handle_scan_broken_resources)

	# New scene/node tools
	http_server.register_route("/api/scene/save", _handle_save_scene)
	http_server.register_route("/api/node/rename", _handle_rename_node)
	http_server.register_route("/api/node/reorder", _handle_reorder_node)
	http_server.register_route("/api/node/find", _handle_find_nodes)
	http_server.register_route("/api/node/signals", _handle_get_node_signals)
	http_server.register_route("/api/node/connect_signal", _handle_connect_signal)
	http_server.register_route("/api/node/disconnect_signal", _handle_disconnect_signal)
	http_server.register_route("/api/node/add_to_group", _handle_add_to_group)
	http_server.register_route("/api/node/remove_from_group", _handle_remove_from_group)
	http_server.register_route("/api/node/get_groups", _handle_get_node_groups)
	http_server.register_route("/api/node/batch_set_properties", _handle_batch_set_properties)
	http_server.register_route("/api/node/class_properties", _handle_get_class_property_list)

	# Runtime tools (fix: these were missing before)
	http_server.register_route("/api/runtime/simulate_key", _handle_simulate_key_press)
	http_server.register_route("/api/runtime/simulate_action", _handle_simulate_action)
	http_server.register_route("/api/runtime/simulate_mouse_button", _handle_simulate_mouse_button)
	http_server.register_route("/api/runtime/simulate_mouse_motion", _handle_simulate_mouse_motion)
	http_server.register_route("/api/runtime/input_actions", _handle_get_input_actions)
	http_server.register_route("/api/runtime/node_properties", _handle_get_node_properties)
	http_server.register_route("/api/runtime/node_methods", _handle_get_node_methods)
	http_server.register_route("/api/runtime/call_method", _handle_call_node_method)
	http_server.register_route("/api/runtime/stats", _handle_get_runtime_stats)
	http_server.register_route("/api/runtime/plugins", _handle_get_installed_plugins)
	http_server.register_route("/api/runtime/plugin_info", _handle_get_plugin_info)
	http_server.register_route("/api/runtime/run_test", _handle_run_test_script)
	http_server.register_route("/api/runtime/assets_by_type", _handle_get_assets_by_type)
	http_server.register_route("/api/runtime/asset_info", _handle_get_asset_info)

	# Shader / material tools
	http_server.register_route("/api/node/set_shader_parameter", _handle_set_shader_parameter)

	# Import settings tools
	http_server.register_route("/api/project/import_settings_get", _handle_get_import_settings)
	http_server.register_route("/api/project/import_settings_set", _handle_set_import_settings)

	# Undo / redo
	http_server.register_route("/api/editor/undo", _handle_undo)
	http_server.register_route("/api/editor/redo", _handle_redo)

	# Navigation mesh baking
	http_server.register_route("/api/scene/bake_navigation", _handle_bake_navigation_mesh)

	# Profiler snapshot
	http_server.register_route("/api/runtime/profiler_snapshot", _handle_get_profiler_snapshot)

	# TileMap tools
	http_server.register_route("/api/tilemap/paint",       _handle_paint_tiles)
	http_server.register_route("/api/tilemap/fill_rect",   _handle_fill_tiles_rect)
	http_server.register_route("/api/tilemap/clear",       _handle_clear_tiles)
	http_server.register_route("/api/tilemap/get_cell",    _handle_get_cell_tile)

	# GridMap tools
	http_server.register_route("/api/gridmap/set_cell",    _handle_set_grid_cell)
	http_server.register_route("/api/gridmap/fill_box",    _handle_fill_grid_box)
	http_server.register_route("/api/gridmap/used_cells",  _handle_get_grid_used_cells)

	# Batch operation tools
	http_server.register_route("/api/batch/set_property_on_type",  _handle_batch_set_property_on_type)
	http_server.register_route("/api/batch/set_property_on_group", _handle_batch_set_property_on_group)
	http_server.register_route("/api/batch/replace_in_scripts",    _handle_replace_in_all_scripts)
	http_server.register_route("/api/batch/create_nodes",          _handle_batch_create_nodes)

	# Animation extras
	http_server.register_route("/api/animation/blend_space/add_point", _handle_add_blend_space_point)
	http_server.register_route("/api/animation/blend_space/info",      _handle_get_blend_space_info)
	http_server.register_route("/api/animation/copy",                  _handle_copy_animation)
	http_server.register_route("/api/animation/set_speed_scale",       _handle_set_animation_speed_scale)

	# QA / Validation tools
	http_server.register_route("/api/qa/assert_no_errors",    _handle_assert_no_errors)
	http_server.register_route("/api/qa/validate_scene",      _handle_validate_scene)
	http_server.register_route("/api/qa/simulate_mouse_path", _handle_simulate_mouse_path)
	http_server.register_route("/api/qa/reimport_all",        _handle_reimport_all)
	http_server.register_route("/api/qa/set_node_unique_name",_handle_set_node_unique_name)

	# Audio tools
	http_server.register_route("/api/audio/create_3d",           _handle_create_audio_player_3d)
	http_server.register_route("/api/audio/play",                _handle_play_audio)
	http_server.register_route("/api/audio/stop",                _handle_stop_audio)
	http_server.register_route("/api/audio/set_property",        _handle_set_audio_property)
	http_server.register_route("/api/audio/playback_position",   _handle_get_playback_position)
	http_server.register_route("/api/audio/set_bus_volume",      _handle_set_bus_volume)
	http_server.register_route("/api/audio/add_bus_effect",      _handle_add_bus_effect)

	# Testing / QA tools
	http_server.register_route("/api/test/action_sequence",  _handle_simulate_action_sequence)
	http_server.register_route("/api/test/wait_frames",      _handle_wait_frames)
	http_server.register_route("/api/test/assert_property",  _handle_assert_node_property)
	http_server.register_route("/api/test/frame_sequence",   _handle_capture_frame_sequence)
	http_server.register_route("/api/test/scene_stats",      _handle_get_scene_statistics)

	# Editor polish tools
	http_server.register_route("/api/editor/select_nodes",       _handle_select_nodes)
	http_server.register_route("/api/editor/batch_duplicate",    _handle_batch_duplicate_with_offset)
	http_server.register_route("/api/editor/find_scripts",       _handle_find_scripts_with_pattern)

	# Physics tools
	http_server.register_route("/api/physics/apply_impulse",       _handle_apply_impulse)
	http_server.register_route("/api/physics/apply_force",         _handle_apply_force)
	http_server.register_route("/api/physics/apply_torque",        _handle_apply_torque)
	http_server.register_route("/api/physics/set_linear_velocity", _handle_set_linear_velocity)
	http_server.register_route("/api/physics/set_angular_velocity",_handle_set_angular_velocity)
	http_server.register_route("/api/physics/set_property",        _handle_set_physics_property)
	http_server.register_route("/api/physics/create_joint",        _handle_create_joint)

	# Particle tools
	http_server.register_route("/api/particles/create",             _handle_create_particles)
	http_server.register_route("/api/particles/set_material_param", _handle_set_particle_material_param)
	http_server.register_route("/api/particles/restart",            _handle_restart_particles)
	http_server.register_route("/api/particles/info",               _handle_get_particle_info)

	# Shader tools
	http_server.register_route("/api/shader/create_material",  _handle_create_shader_material)
	http_server.register_route("/api/shader/get_code",         _handle_get_shader_code)
	http_server.register_route("/api/shader/set_code",         _handle_set_shader_code)
	http_server.register_route("/api/shader/get_parameters",   _handle_get_shader_parameters)

	# Animation tools
	http_server.register_route("/api/animation/player_info",         _handle_get_animation_player_info)
	http_server.register_route("/api/animation/create",              _handle_create_animation)
	http_server.register_route("/api/animation/info",                _handle_get_animation_info)
	http_server.register_route("/api/animation/set_properties",      _handle_set_animation_properties)
	http_server.register_route("/api/animation/delete",              _handle_delete_animation)
	http_server.register_route("/api/animation/track/add",           _handle_add_animation_track)
	http_server.register_route("/api/animation/track/remove",        _handle_remove_animation_track)
	http_server.register_route("/api/animation/track/set_path",      _handle_set_track_path)
	http_server.register_route("/api/animation/track/info",          _handle_get_track_info)
	http_server.register_route("/api/animation/track/set_interp",    _handle_set_track_interpolation)
	http_server.register_route("/api/animation/keyframe/add",        _handle_add_keyframe)
	http_server.register_route("/api/animation/keyframe/remove",     _handle_remove_keyframe)
	http_server.register_route("/api/animation/keyframe/set_value",  _handle_set_keyframe_value)
	http_server.register_route("/api/animation/keyframe/set_time",   _handle_set_keyframe_time)
	http_server.register_route("/api/animation/keyframe/list",       _handle_get_keyframes)
	http_server.register_route("/api/animation/tree/setup",          _handle_setup_animation_tree)
	http_server.register_route("/api/animation/tree/add_state",      _handle_add_state_to_machine)
	http_server.register_route("/api/animation/tree/connect_states", _handle_connect_states)
	http_server.register_route("/api/animation/tree/set_blend",      _handle_set_blend_parameter)
	http_server.register_route("/api/animation/tree/travel",         _handle_travel_to_state)

	# Skeleton tools
	http_server.register_route("/api/skeleton/get_bones",     _handle_get_skeleton_bones)
	http_server.register_route("/api/skeleton/set_bone_pose", _handle_set_bone_pose)
	http_server.register_route("/api/skeleton/reset_pose",    _handle_reset_skeleton_pose)

	# Batch extras
	http_server.register_route("/api/batch/attach_script",    _handle_batch_attach_script)
	http_server.register_route("/api/batch/rename_nodes",     _handle_batch_rename_nodes)
	http_server.register_route("/api/batch/move_file",        _handle_move_and_rename_file)
	http_server.register_route("/api/batch/pack_scene",       _handle_pack_scene)
	http_server.register_route("/api/batch/create_resource",  _handle_create_resource_file)

	# Project utility tools
	http_server.register_route("/api/project/assert_fps",        _handle_assert_fps_above)
	http_server.register_route("/api/project/renderer_info",     _handle_get_renderer_info)
	http_server.register_route("/api/project/assert_resource",   _handle_assert_resource_valid)
	http_server.register_route("/api/project/node_global_xform", _handle_get_node_global_transform)
	http_server.register_route("/api/project/set_global_xform",  _handle_set_node_global_transform)
	http_server.register_route("/api/project/feature_tag",       _handle_toggle_feature_tag)
	http_server.register_route("/api/project/node_metadata",     _handle_set_node_metadata)


func _create_bottom_panel() -> void:
	bottom_panel = preload("res://addons/godot_mcp_enhanced/ui/bottom_panel.tscn").instantiate()
	add_control_to_bottom_panel(bottom_panel, "MCP Enhanced")
	
	# Connect signals
	bottom_panel.connect("config_changed", _on_config_changed)
	bottom_panel.connect("server_restart_requested", _on_server_restart_requested)
	
	# Update UI with current config
	bottom_panel.update_config_display(config)


# HTTP Route Handlers - Project Tools
func _handle_get_project_info(params: Dictionary) -> Dictionary:
	var project_info = {
		"name": ProjectSettings.get_setting("application/config/name", "Unknown Project"),
		"version": ProjectSettings.get_setting("application/config/version", "1.0"),
		"godot_version": Engine.get_version_info(),
		"project_path": ProjectSettings.globalize_path("res://"),
		"main_scene": ProjectSettings.get_setting("application/run/main_scene", ""),
		"features": ProjectSettings.get_setting("application/config/features", []),
		"auto_accept_quit": ProjectSettings.get_setting("application/config/auto_accept_quit", true)
	}
	return {"success": true, "data": project_info}


func _handle_get_filesystem_tree(params: Dictionary) -> Dictionary:
	var filters = params.get("filters", [])
	var tree = file_operations.get_filesystem_tree("res://", filters)
	return {"success": true, "data": tree}


func _handle_search_files(params: Dictionary) -> Dictionary:
	var query = params.get("query", "")
	var results = file_operations.search_files(query)
	return {"success": true, "data": results}


func _handle_uid_to_project_path(params: Dictionary) -> Dictionary:
	var uid = params.get("uid", "")
	var path = file_operations.uid_to_project_path(uid)
	return {"success": true, "data": {"path": path}}


func _handle_project_path_to_uid(params: Dictionary) -> Dictionary:
	var path = params.get("path", "")
	var uid = file_operations.project_path_to_uid(path)
	return {"success": true, "data": {"uid": uid}}


func _handle_update_project_settings(params: Dictionary) -> Dictionary:
	var settings = params.get("settings", {})
	if typeof(settings) != TYPE_DICTIONARY:
		return {"success": false, "error": "settings must be a dictionary"}
	return file_operations.update_project_settings_values(settings)


func _handle_write_text_file(params: Dictionary) -> Dictionary:
	var path = params.get("path", params.get("file_path", ""))
	var content = params.get("content", "")
	if path == "":
		return {"success": false, "error": "path is required"}
	return file_operations.write_text_file(path, content)


func _handle_create_directory(params: Dictionary) -> Dictionary:
	var dir_path = params.get("dir_path", params.get("path", ""))
	if dir_path == "":
		return {"success": false, "error": "dir_path is required"}
	return file_operations.create_directory(dir_path)


# HTTP Route Handlers - Scene Tools
func _handle_get_scene_tree(params: Dictionary) -> Dictionary:
	var tree = scene_operations.get_scene_tree()
	return {"success": true, "data": tree}


func _handle_get_scene_file_content(params: Dictionary) -> Dictionary:
	var content = scene_operations.get_scene_file_content()
	return {"success": true, "data": {"content": content}}


func _handle_create_scene(params: Dictionary) -> Dictionary:
	var scene_path = params.get("scene_path", "")
	var root_type = params.get("root_type", "Node2D")
	var result = scene_operations.create_scene(scene_path, root_type)
	return result


func _handle_open_scene(params: Dictionary) -> Dictionary:
	var scene_path = params.get("scene_path", "")
	var result = scene_operations.open_scene(scene_path)
	return result


func _handle_delete_scene(params: Dictionary) -> Dictionary:
	var scene_path = params.get("scene_path", "")
	var result = scene_operations.delete_scene(scene_path)
	return result


func _handle_add_scene(params: Dictionary) -> Dictionary:
	var scene_path = params.get("scene_path", "")
	var parent_node = params.get("parent_node", "")
	var result = scene_operations.add_scene_as_child(scene_path, parent_node)
	return result


func _handle_play_scene(params: Dictionary) -> Dictionary:
	var scene_path = params.get("scene_path", "")
	var result = scene_operations.play_scene(scene_path)
	return result


func _handle_stop_running_scene(params: Dictionary) -> Dictionary:
	var result = scene_operations.stop_running_scene()
	return result


# HTTP Route Handlers - Node Tools
func _handle_add_node(params: Dictionary) -> Dictionary:
	return scene_operations.add_node(params)


func _handle_delete_node(params: Dictionary) -> Dictionary:
	return scene_operations.delete_node(params)


func _handle_duplicate_node(params: Dictionary) -> Dictionary:
	return scene_operations.duplicate_node(params)


func _handle_move_node(params: Dictionary) -> Dictionary:
	return scene_operations.move_node(params)


func _handle_update_property(params: Dictionary) -> Dictionary:
	return scene_operations.update_property(params)


func _handle_add_resource(params: Dictionary) -> Dictionary:
	return scene_operations.add_resource(params)


func _handle_set_anchor_preset(params: Dictionary) -> Dictionary:
	return scene_operations.set_anchor_preset(params)


func _handle_set_anchor_values(params: Dictionary) -> Dictionary:
	return scene_operations.set_anchor_values(params)


# HTTP Route Handlers - Script Tools
func _handle_get_open_scripts(params: Dictionary) -> Dictionary:
	return script_operations.get_open_scripts()


func _handle_view_script(params: Dictionary) -> Dictionary:
	return script_operations.view_script(params)


func _handle_create_script(params: Dictionary) -> Dictionary:
	return script_operations.create_script(params)


func _handle_attach_script(params: Dictionary) -> Dictionary:
	return script_operations.attach_script(params)


func _handle_edit_file(params: Dictionary) -> Dictionary:
	return script_operations.edit_file(params)


# HTTP Route Handlers - Editor Tools
func _handle_get_godot_errors(params: Dictionary) -> Dictionary:
	return debugger_integration.get_errors()


func _handle_get_editor_screenshot(params: Dictionary) -> Dictionary:
	var screenshot_data = screenshot_manager.capture_editor_screenshot()
	return {"success": true, "data": {"screenshot": screenshot_data}}


func _handle_get_running_scene_screenshot(params: Dictionary) -> Dictionary:
	var screenshot_data = screenshot_manager.capture_running_scene_screenshot()
	return {"success": true, "data": {"screenshot": screenshot_data}}


func _handle_execute_editor_script(params: Dictionary) -> Dictionary:
	var code = params.get("code", "")
	return script_operations.execute_editor_script(code)


func _handle_clear_output_logs(params: Dictionary) -> Dictionary:
	return debugger_integration.clear_logs()


# Windsurf-specific handlers
func _handle_get_windsurf_context(params: Dictionary) -> Dictionary:
	var context = {
		"current_scene": get_editor_interface().get_edited_scene_root().get_name() if get_editor_interface().get_edited_scene_root() else null,
		"open_scripts": script_operations.get_open_script_names(),
		"recent_errors": debugger_integration.get_recent_errors(5),
		"project_structure": file_operations.get_quick_project_overview(),
		"editor_state": {
			"playing": get_editor_interface().is_playing_scene(),
			"distraction_free": get_editor_interface().is_distraction_free_mode_enabled()
		}
	}
	return {"success": true, "data": context}


func _handle_get_live_preview(params: Dictionary) -> Dictionary:
	var preview_data = {
		"screenshot": screenshot_manager.capture_editor_screenshot(),
		"scene_tree": scene_operations.get_compact_scene_tree(),
		"current_script": script_operations.get_current_script_content()
	}
	return {"success": true, "data": preview_data}


# Signal handlers
func _on_config_changed(new_config: Dictionary) -> void:
	config = new_config
	_save_config()


func _on_server_restart_requested() -> void:
	print("[Godot MCP Enhanced] ========================================")
	print("[Godot MCP Enhanced] Restarting server...")

	# Stop server
	http_server.stop_server()
	if bottom_panel:
		bottom_panel.update_server_status(false)

	print("[Godot MCP Enhanced] Server stopped, waiting 1 second...")
	await get_tree().create_timer(1.0).timeout

	# Start server
	var port = int(config.get("GDAI_MCP_SERVER_PORT", 3571))
	print("[Godot MCP Enhanced] Starting server on port %d..." % port)

	var success = http_server.start_server(port)

	if success:
		print("[Godot MCP Enhanced] ✓ Server restarted successfully on port %d" % port)
		if bottom_panel:
			bottom_panel.update_server_status(true)
	else:
		push_error("[Godot MCP Enhanced] ✗ Failed to restart server on port %d!" % port)
		push_error("[Godot MCP Enhanced] Check if port is already in use")
		if bottom_panel:
			bottom_panel.update_server_status(false)

	print("[Godot MCP Enhanced] ========================================")


# Autoload handlers
func _handle_get_autoloads(params: Dictionary) -> Dictionary:
	var autoloads = []
	for prop in ProjectSettings.get_property_list():
		if prop.name.begins_with("autoload/"):
			var name = prop.name.substr("autoload/".length())
			var value = ProjectSettings.get_setting(prop.name, "")
			autoloads.append({
				"name": name,
				"path": value.trim_prefix("*"),
				"singleton": value.begins_with("*")
			})
	return {"success": true, "data": {"autoloads": autoloads}}


func _handle_add_autoload(params: Dictionary) -> Dictionary:
	var name = params.get("name", "")
	var path = params.get("path", "")
	var singleton = params.get("singleton", true)

	if name == "" or path == "":
		return {"success": false, "error": "name and path are required"}

	get_editor_interface().get_editor_settings()
	var value = ("*" if singleton else "") + path
	ProjectSettings.set_setting("autoload/" + name, value)
	ProjectSettings.save()
	return {"success": true, "data": {"name": name, "path": path}}


func _handle_remove_autoload(params: Dictionary) -> Dictionary:
	var name = params.get("name", "")
	if name == "":
		return {"success": false, "error": "name is required"}

	var key = "autoload/" + name
	if not ProjectSettings.has_setting(key):
		return {"success": false, "error": "Autoload not found: " + name}

	ProjectSettings.set_setting(key, null)
	ProjectSettings.save()
	return {"success": true}


func _handle_set_main_scene(params: Dictionary) -> Dictionary:
	var scene_path = params.get("scene_path", "")
	if scene_path == "":
		return {"success": false, "error": "scene_path is required"}
	if not scene_path.begins_with("res://"):
		scene_path = "res://" + scene_path
	if not FileAccess.file_exists(scene_path):
		return {"success": false, "error": "Scene not found: " + scene_path}

	ProjectSettings.set_setting("application/run/main_scene", scene_path)
	ProjectSettings.save()
	return {"success": true, "data": {"main_scene": scene_path}}


# New scene/node handlers
func _handle_save_scene(params: Dictionary) -> Dictionary:
	return scene_operations.save_scene()


func _handle_rename_node(params: Dictionary) -> Dictionary:
	return scene_operations.rename_node(params)


func _handle_reorder_node(params: Dictionary) -> Dictionary:
	return scene_operations.reorder_node(params)


func _handle_find_nodes(params: Dictionary) -> Dictionary:
	return scene_operations.find_nodes(params)


func _handle_get_node_signals(params: Dictionary) -> Dictionary:
	return scene_operations.get_node_signals(params)


func _handle_connect_signal(params: Dictionary) -> Dictionary:
	return scene_operations.connect_signal(params)


func _handle_disconnect_signal(params: Dictionary) -> Dictionary:
	return scene_operations.disconnect_signal(params)


func _handle_add_to_group(params: Dictionary) -> Dictionary:
	return scene_operations.add_node_to_group(params)


func _handle_remove_from_group(params: Dictionary) -> Dictionary:
	return scene_operations.remove_node_from_group(params)


func _handle_get_node_groups(params: Dictionary) -> Dictionary:
	return scene_operations.get_node_groups(params)


func _handle_batch_set_properties(params: Dictionary) -> Dictionary:
	return scene_operations.batch_set_properties(params)


func _handle_get_class_property_list(params: Dictionary) -> Dictionary:
	return scene_operations.get_class_property_list(params)


# Runtime handlers (fix: these were missing)
func _handle_simulate_key_press(params: Dictionary) -> Dictionary:
	var keycode = params.get("keycode", 0)
	var pressed = params.get("pressed", true)
	return runtime_operations.simulate_key_press(keycode, pressed)


func _handle_simulate_action(params: Dictionary) -> Dictionary:
	var action_name = params.get("action_name", "")
	var pressed = params.get("pressed", true)
	var strength = float(params.get("strength", 1.0))
	return runtime_operations.simulate_action(action_name, pressed, strength)


func _handle_simulate_mouse_button(params: Dictionary) -> Dictionary:
	var button_index = params.get("button_index", 1)
	var pressed = params.get("pressed", true)
	var pos_x = float(params.get("position_x", 0.0))
	var pos_y = float(params.get("position_y", 0.0))
	return runtime_operations.simulate_mouse_button(button_index, pressed, Vector2(pos_x, pos_y))


func _handle_simulate_mouse_motion(params: Dictionary) -> Dictionary:
	var pos_x = float(params.get("position_x", 0.0))
	var pos_y = float(params.get("position_y", 0.0))
	var rel_x = float(params.get("relative_x", 0.0))
	var rel_y = float(params.get("relative_y", 0.0))
	return runtime_operations.simulate_mouse_motion(Vector2(pos_x, pos_y), Vector2(rel_x, rel_y))


func _handle_get_input_actions(params: Dictionary) -> Dictionary:
	return runtime_operations.get_input_actions()


func _handle_get_node_properties(params: Dictionary) -> Dictionary:
	var node_path = params.get("node_path", "")
	return runtime_operations.get_node_properties(node_path)


func _handle_get_node_methods(params: Dictionary) -> Dictionary:
	var node_path = params.get("node_path", "")
	return runtime_operations.get_node_methods(node_path)


func _handle_call_node_method(params: Dictionary) -> Dictionary:
	var node_path = params.get("node_path", "")
	var method_name = params.get("method_name", "")
	var args = params.get("args", [])
	return runtime_operations.call_node_method(node_path, method_name, args)


func _handle_get_runtime_stats(params: Dictionary) -> Dictionary:
	return runtime_operations.get_runtime_stats()


func _handle_get_installed_plugins(params: Dictionary) -> Dictionary:
	return runtime_operations.get_installed_plugins()


func _handle_get_plugin_info(params: Dictionary) -> Dictionary:
	var plugin_name = params.get("plugin_name", "")
	return runtime_operations.get_plugin_info(plugin_name)


func _handle_run_test_script(params: Dictionary) -> Dictionary:
	var script_path = params.get("script_path", "")
	return runtime_operations.run_test_script(script_path)


func _handle_get_assets_by_type(params: Dictionary) -> Dictionary:
	var asset_type = params.get("asset_type", "texture")
	return runtime_operations.get_assets_by_type(asset_type)


func _handle_get_asset_info(params: Dictionary) -> Dictionary:
	var asset_path = params.get("asset_path", "")
	return runtime_operations.get_asset_info(asset_path)


func _handle_set_shader_parameter(params: Dictionary) -> Dictionary:
	return scene_operations.set_shader_parameter(params)


func _handle_scan_broken_resources(params: Dictionary) -> Dictionary:
	return scene_operations.scan_broken_resources()


# Import settings handlers
func _handle_get_import_settings(params: Dictionary) -> Dictionary:
	var resource_path = params.get("resource_path", "")
	return file_operations.get_import_settings(resource_path)


func _handle_set_import_settings(params: Dictionary) -> Dictionary:
	var resource_path = params.get("resource_path", "")
	var settings = params.get("params", {})
	return file_operations.set_import_settings(resource_path, settings)


# Undo / Redo handlers
func _handle_undo(params: Dictionary) -> Dictionary:
	var undo_redo = get_undo_redo()
	if not undo_redo:
		return {"success": false, "error": "EditorUndoRedoManager not available"}
	var scene_root = get_editor_interface().get_edited_scene_root()
	if scene_root:
		var history_id = undo_redo.get_object_history_id(scene_root)
		var ur = undo_redo.get_history_undo_redo(history_id)
		if ur and ur.has_undo():
			ur.undo()
			return {"success": true, "data": {"message": "Undid last scene action"}}
		else:
			return {"success": false, "error": "Nothing to undo in scene history"}
	return {"success": false, "error": "No scene open"}


func _handle_redo(params: Dictionary) -> Dictionary:
	var undo_redo = get_undo_redo()
	if not undo_redo:
		return {"success": false, "error": "EditorUndoRedoManager not available"}
	var scene_root = get_editor_interface().get_edited_scene_root()
	if scene_root:
		var history_id = undo_redo.get_object_history_id(scene_root)
		var ur = undo_redo.get_history_undo_redo(history_id)
		if ur and ur.has_redo():
			ur.redo()
			return {"success": true, "data": {"message": "Redid last undone scene action"}}
		else:
			return {"success": false, "error": "Nothing to redo in scene history"}
	return {"success": false, "error": "No scene open"}


# Navigation mesh baking handler
func _handle_bake_navigation_mesh(params: Dictionary) -> Dictionary:
	return await scene_operations.bake_navigation_mesh(params)


# Profiler snapshot handler
func _handle_get_profiler_snapshot(params: Dictionary) -> Dictionary:
	var frame_count = int(params.get("frame_count", 60))
	return await runtime_operations.get_profiler_snapshot(frame_count)


# ── Animation handlers ────────────────────────────────────────────────────────

func _handle_get_animation_player_info(params: Dictionary) -> Dictionary:
	return animation_operations.get_animation_player_info(params)

func _handle_create_animation(params: Dictionary) -> Dictionary:
	return animation_operations.create_animation(params)

func _handle_get_animation_info(params: Dictionary) -> Dictionary:
	return animation_operations.get_animation_info(params)

func _handle_set_animation_properties(params: Dictionary) -> Dictionary:
	return animation_operations.set_animation_properties(params)

func _handle_delete_animation(params: Dictionary) -> Dictionary:
	return animation_operations.delete_animation(params)

func _handle_add_animation_track(params: Dictionary) -> Dictionary:
	return animation_operations.add_animation_track(params)

func _handle_remove_animation_track(params: Dictionary) -> Dictionary:
	return animation_operations.remove_animation_track(params)

func _handle_set_track_path(params: Dictionary) -> Dictionary:
	return animation_operations.set_track_path(params)

func _handle_get_track_info(params: Dictionary) -> Dictionary:
	return animation_operations.get_track_info(params)

func _handle_set_track_interpolation(params: Dictionary) -> Dictionary:
	return animation_operations.set_track_interpolation(params)

func _handle_add_keyframe(params: Dictionary) -> Dictionary:
	return animation_operations.add_keyframe(params)

func _handle_remove_keyframe(params: Dictionary) -> Dictionary:
	return animation_operations.remove_keyframe(params)

func _handle_set_keyframe_value(params: Dictionary) -> Dictionary:
	return animation_operations.set_keyframe_value(params)

func _handle_set_keyframe_time(params: Dictionary) -> Dictionary:
	return animation_operations.set_keyframe_time(params)

func _handle_get_keyframes(params: Dictionary) -> Dictionary:
	return animation_operations.get_keyframes(params)

func _handle_setup_animation_tree(params: Dictionary) -> Dictionary:
	return animation_operations.setup_animation_tree(params)

func _handle_add_state_to_machine(params: Dictionary) -> Dictionary:
	return animation_operations.add_state_to_machine(params)

func _handle_connect_states(params: Dictionary) -> Dictionary:
	return animation_operations.connect_states(params)

func _handle_set_blend_parameter(params: Dictionary) -> Dictionary:
	return animation_operations.set_blend_parameter(params)

func _handle_travel_to_state(params: Dictionary) -> Dictionary:
	return animation_operations.travel_to_state(params)


# ── Physics handlers ──────────────────────────────────────────────────────────

func _handle_apply_impulse(params: Dictionary) -> Dictionary:
	return physics_operations.apply_impulse(params)

func _handle_apply_force(params: Dictionary) -> Dictionary:
	return physics_operations.apply_force(params)

func _handle_apply_torque(params: Dictionary) -> Dictionary:
	return physics_operations.apply_torque(params)

func _handle_set_linear_velocity(params: Dictionary) -> Dictionary:
	return physics_operations.set_linear_velocity(params)

func _handle_set_angular_velocity(params: Dictionary) -> Dictionary:
	return physics_operations.set_angular_velocity(params)

func _handle_set_physics_property(params: Dictionary) -> Dictionary:
	return physics_operations.set_physics_property(params)

func _handle_create_joint(params: Dictionary) -> Dictionary:
	return physics_operations.create_joint(params)


# ── Particle handlers ─────────────────────────────────────────────────────────

func _handle_create_particles(params: Dictionary) -> Dictionary:
	return particles_operations.create_particles(params)

func _handle_set_particle_material_param(params: Dictionary) -> Dictionary:
	return particles_operations.set_particle_material_param(params)

func _handle_restart_particles(params: Dictionary) -> Dictionary:
	return particles_operations.restart_particles(params)

func _handle_get_particle_info(params: Dictionary) -> Dictionary:
	return particles_operations.get_particle_info(params)


# ── Shader handlers ───────────────────────────────────────────────────────────

func _handle_create_shader_material(params: Dictionary) -> Dictionary:
	return shader_operations.create_shader_material(params)

func _handle_get_shader_code(params: Dictionary) -> Dictionary:
	return shader_operations.get_shader_code(params)

func _handle_set_shader_code(params: Dictionary) -> Dictionary:
	return shader_operations.set_shader_code(params)

func _handle_get_shader_parameters(params: Dictionary) -> Dictionary:
	return shader_operations.get_shader_parameters(params)


# ── Audio handlers ────────────────────────────────────────────────────────────

func _handle_create_audio_player_3d(params: Dictionary) -> Dictionary:
	return audio_operations.create_audio_player_3d(params)

func _handle_play_audio(params: Dictionary) -> Dictionary:
	return audio_operations.play_audio(params)

func _handle_stop_audio(params: Dictionary) -> Dictionary:
	return audio_operations.stop_audio(params)

func _handle_set_audio_property(params: Dictionary) -> Dictionary:
	return audio_operations.set_audio_property(params)

func _handle_get_playback_position(params: Dictionary) -> Dictionary:
	return audio_operations.get_playback_position(params)

func _handle_set_bus_volume(params: Dictionary) -> Dictionary:
	return audio_operations.set_bus_volume(params)

func _handle_add_bus_effect(params: Dictionary) -> Dictionary:
	return audio_operations.add_bus_effect(params)


# ── Testing / QA handlers ─────────────────────────────────────────────────────

func _handle_simulate_action_sequence(params: Dictionary) -> Dictionary:
	return await testing_operations.simulate_action_sequence(params)

func _handle_wait_frames(params: Dictionary) -> Dictionary:
	return await testing_operations.wait_frames(params)

func _handle_assert_node_property(params: Dictionary) -> Dictionary:
	return testing_operations.assert_node_property(params)

func _handle_capture_frame_sequence(params: Dictionary) -> Dictionary:
	return await testing_operations.capture_frame_sequence(params)

func _handle_get_scene_statistics(params: Dictionary) -> Dictionary:
	return testing_operations.get_scene_statistics(params)


# ── Editor polish handlers ────────────────────────────────────────────────────

func _handle_select_nodes(params: Dictionary) -> Dictionary:
	return editor_polish_operations.select_nodes(params)

func _handle_batch_duplicate_with_offset(params: Dictionary) -> Dictionary:
	return editor_polish_operations.batch_duplicate_with_offset(params)

func _handle_find_scripts_with_pattern(params: Dictionary) -> Dictionary:
	return editor_polish_operations.find_scripts_with_pattern(params)


# ── TileMap handlers ──────────────────────────────────────────────────────────

func _handle_paint_tiles(params: Dictionary) -> Dictionary:
	return tilemap_operations.paint_tiles(params)

func _handle_fill_tiles_rect(params: Dictionary) -> Dictionary:
	return tilemap_operations.fill_tiles_rect(params)

func _handle_clear_tiles(params: Dictionary) -> Dictionary:
	return tilemap_operations.clear_tiles(params)

func _handle_get_cell_tile(params: Dictionary) -> Dictionary:
	return tilemap_operations.get_cell_tile(params)


# ── GridMap handlers ──────────────────────────────────────────────────────────

func _handle_set_grid_cell(params: Dictionary) -> Dictionary:
	return tilemap_operations.set_grid_cell(params)

func _handle_fill_grid_box(params: Dictionary) -> Dictionary:
	return tilemap_operations.fill_grid_box(params)

func _handle_get_grid_used_cells(params: Dictionary) -> Dictionary:
	return tilemap_operations.get_grid_used_cells(params)


# ── Batch operation handlers ──────────────────────────────────────────────────

func _handle_batch_set_property_on_type(params: Dictionary) -> Dictionary:
	return batch_operations.batch_set_property_on_type(params)

func _handle_batch_set_property_on_group(params: Dictionary) -> Dictionary:
	return batch_operations.batch_set_property_on_group(params)

func _handle_replace_in_all_scripts(params: Dictionary) -> Dictionary:
	return batch_operations.replace_in_all_scripts(params)

func _handle_batch_create_nodes(params: Dictionary) -> Dictionary:
	return batch_operations.batch_create_nodes(params)


# ── Animation extras handlers ─────────────────────────────────────────────────

func _handle_add_blend_space_point(params: Dictionary) -> Dictionary:
	return animation_extras.add_blend_space_point(params)

func _handle_get_blend_space_info(params: Dictionary) -> Dictionary:
	return animation_extras.get_blend_space_info(params)

func _handle_copy_animation(params: Dictionary) -> Dictionary:
	return animation_extras.copy_animation(params)

func _handle_set_animation_speed_scale(params: Dictionary) -> Dictionary:
	return animation_extras.set_animation_speed_scale(params)


# ── QA / Validation handlers ──────────────────────────────────────────────────

func _handle_assert_no_errors(params: Dictionary) -> Dictionary:
	return qa_validation_operations.assert_no_errors(params)

func _handle_validate_scene(params: Dictionary) -> Dictionary:
	return qa_validation_operations.validate_scene(params)

func _handle_simulate_mouse_path(params: Dictionary) -> Dictionary:
	return await qa_validation_operations.simulate_mouse_path(params)

func _handle_reimport_all(params: Dictionary) -> Dictionary:
	return qa_validation_operations.reimport_all(params)

func _handle_set_node_unique_name(params: Dictionary) -> Dictionary:
	return qa_validation_operations.set_node_unique_name(params)


# ── Skeleton handlers ─────────────────────────────────────────────────────────

func _handle_get_skeleton_bones(params: Dictionary) -> Dictionary:
	return skeleton_operations.get_skeleton_bones(params)

func _handle_set_bone_pose(params: Dictionary) -> Dictionary:
	return skeleton_operations.set_bone_pose(params)

func _handle_reset_skeleton_pose(params: Dictionary) -> Dictionary:
	return skeleton_operations.reset_skeleton_pose(params)


# ── Batch extras handlers ─────────────────────────────────────────────────────

func _handle_batch_attach_script(params: Dictionary) -> Dictionary:
	return batch_extras.batch_attach_script(params)

func _handle_batch_rename_nodes(params: Dictionary) -> Dictionary:
	return batch_extras.batch_rename_nodes(params)

func _handle_move_and_rename_file(params: Dictionary) -> Dictionary:
	return batch_extras.move_and_rename_file(params)

func _handle_pack_scene(params: Dictionary) -> Dictionary:
	return batch_extras.pack_scene(params)

func _handle_create_resource_file(params: Dictionary) -> Dictionary:
	return batch_extras.create_resource_file(params)


# ── Project utility handlers ──────────────────────────────────────────────────

func _handle_assert_fps_above(params: Dictionary) -> Dictionary:
	return await project_utils.assert_fps_above(params)

func _handle_get_renderer_info(params: Dictionary) -> Dictionary:
	return project_utils.get_renderer_info(params)

func _handle_assert_resource_valid(params: Dictionary) -> Dictionary:
	return project_utils.assert_resource_valid(params)

func _handle_get_node_global_transform(params: Dictionary) -> Dictionary:
	return project_utils.get_node_global_transform(params)

func _handle_set_node_global_transform(params: Dictionary) -> Dictionary:
	return project_utils.set_node_global_transform(params)

func _handle_toggle_feature_tag(params: Dictionary) -> Dictionary:
	return project_utils.toggle_feature_tag(params)

func _handle_set_node_metadata(params: Dictionary) -> Dictionary:
	return project_utils.set_node_metadata(params)
