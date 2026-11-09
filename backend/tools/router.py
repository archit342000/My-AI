from flask import Blueprint, request, jsonify, Response
import json
import logging
from backend.auth.context import admin_required, current_user_id
from backend.auth.ownership import require_chat_owner
from backend.tools.callbacks import callback_registry
from backend.logging import log_event
from backend.utils import read_json_object

logger = logging.getLogger(__name__)
tools_bp = Blueprint('tools', __name__)

@tools_bp.route('/active/<chat_id>', methods=['GET'])
def get_active_callbacks(chat_id):
    """
    Returns a list of callback IDs that are currently suspended and waiting
    for user input in the specified chat.
    
    Checks both in-memory callbacks AND DB-persisted callbacks (for crash recovery).
    """
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    callback_registry.clear_expired()
    
    # In-memory callbacks
    in_memory = {
        cb_id for cb_id, entry in callback_registry._callbacks.items()
        if entry.get('chat_id') == chat_id and entry.get('response') is None
    }
    
    # DB-persisted callbacks (may exist without in-memory counterpart after restart)
    db_ids = set()
    try:
        from backend.database import db
        db_pending = db.get_pending_callbacks(chat_id)
        db_ids = {cb['callback_id'] for cb in db_pending}
    except Exception as e:
        logger.warning(f"Failed to check DB callbacks for {chat_id}: {e}")
    
    all_active = list(in_memory | db_ids)
    
    # Filter out callbacks that already have a tool result in message history
    # (handles the case where the callback was resolved but cleanup didn't complete)
    if all_active:
        try:
            all_messages = db.get_messages(chat_id)
            # Also check sub-agent messages
            sub_messages = db.get_messages(chat_id, parent_type='research')
            combined = all_messages + sub_messages
            resolved_tool_ids = {
                m.get('tool_call_id') for m in combined
                if m.get('role') == 'tool' and m.get('tool_call_id')
            }
            # Clean up stale DB entries while we're at it
            stale = [cb_id for cb_id in all_active if cb_id in resolved_tool_ids]
            for cb_id in stale:
                db.cleanup_callback(cb_id)
            all_active = [cb_id for cb_id in all_active if cb_id not in resolved_tool_ids]
        except Exception as e:
            logger.warning(f"Failed to filter resolved callbacks for {chat_id}: {e}")

    return jsonify({"active_callback_ids": all_active})

@tools_bp.route('/clarification/response', methods=['POST'])
def clarification_response():
    """
    Unified endpoint for submitting user responses to clarification requests.
    Used by both main chat and sub-agents.
    
    Resolves both in-memory and DB-persisted callbacks.
    """
    callback_registry.clear_expired() # Periodic cleanup
    
    data, err = read_json_object()
    if err:
        return err
    cb_id = data.get('callback_id')
    
    if not cb_id:
        return jsonify({"error": "callback_id required"}), 400
    
    # Find the chat the callback belongs to and check the caller owns it before resolving anything.
    from backend.database import db
    entry = callback_registry.get(cb_id)
    try:
        callback_chat_id = entry.get('chat_id') if entry else db.get_callback_chat_id(cb_id)
    except Exception as e:
        logger.error(f"Failed to look up callback {cb_id}: {e}")
        callback_chat_id = None
    if callback_chat_id is None:
        return jsonify({"error": "Unknown or expired callback_id"}), 404
    if require_chat_owner(callback_chat_id):
        # Same answer as an unknown callback, so ids of other users' callbacks cannot be probed.
        return jsonify({"error": "Unknown or expired callback_id"}), 404

    # Check in-memory first
    if entry:
        # In-memory callback exists (normal case) — resolve it
        callback_registry.resolve(cb_id, data)
        log_event("clarification_resolved", {"callback_id": cb_id, "chat_id": entry.get('chat_id')})
        return jsonify({"success": True})
    
    # No in-memory callback — try DB (crash recovery case: server restarted,
    # user is responding to a persisted callback)
    try:
        db.resolve_callback(cb_id, json.dumps(data))
        log_event("clarification_resolved_db", {"callback_id": cb_id})
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to resolve callback {cb_id}: {e}")
        return jsonify({"error": "Unknown or expired callback_id"}), 404

# --- User Preferences CRUD Routes ---

@tools_bp.route('/preferences', methods=['GET'])
def get_preferences():
    from backend.database import db
    try:
        prefs = db.get_all_preferences(current_user_id())
        return jsonify({"success": True, "preferences": prefs})
    except Exception as e:
        logger.exception("Failed to load preferences")
        log_event("tools_preferences_get_error", {"error": str(e)})
        return jsonify({"error": "Failed to load preferences"}), 500

@tools_bp.route('/preferences', methods=['POST'])
def add_preference():
    from backend.database import db
    data, err = read_json_object()
    if err:
        return err
    content = data.get('content')
    tag = data.get('tag')
    if not content or not tag:
        return jsonify({"error": "Missing content or tag"}), 400
    pref_id = db.add_preference(content, tag, current_user_id())
    return jsonify({"success": True, "id": pref_id})

@tools_bp.route('/preferences/<preference_id>', methods=['PUT'])
def update_preference(preference_id):
    from backend.database import db
    data, err = read_json_object()
    if err:
        return err
    content = data.get('content')
    tag = data.get('tag')
    if not content or not tag:
        return jsonify({"error": "Missing content or tag"}), 400
    success = db.update_preference(preference_id, content, tag, current_user_id())
    if success:
        return jsonify({"success": True})
    log_event("tools_preference_update_not_found", {"preference_id": preference_id})
    return jsonify({"error": "Preference not found"}), 404

@tools_bp.route('/preferences/<preference_id>', methods=['DELETE'])
def delete_preference(preference_id):
    from backend.database import db
    success = db.delete_preference(preference_id, current_user_id())
    if success:
        return jsonify({"success": True})
    log_event("tools_preference_delete_not_found", {"preference_id": preference_id})
    return jsonify({"error": "Preference not found"}), 404

@tools_bp.route('/preferences/reset', methods=['POST'])
def reset_preferences():
    from backend.database import db
    try:
        deleted = db.clear_preferences(current_user_id())
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        logger.exception("Failed to reset preferences")
        log_event("tools_preferences_reset_error", {"error": str(e)})
        return jsonify({"error": "Failed to reset preferences"}), 500

# --- Agent Config Routes ---

@tools_bp.route('/config/agents', methods=['GET'])
@admin_required
def get_agents_config():
    from backend import config
    from backend.chat.agent_handler import AGENT_PROFILES
    
    return jsonify({
        "search_web": {
            "thinking_profile": AGENT_PROFILES.get("search_web", "none"),
            "max_tokens": config.SEARCH_WEB_AGENT_MAX_TOKENS,
            "thinking_budget": config.SEARCH_WEB_AGENT_THINKING_BUDGET
        },
        "document_agent": {
            "thinking_profile": AGENT_PROFILES.get("document_agent", "precision"),
            "max_tokens": config.DOCUMENT_AGENT_MAX_TOKENS,
            "thinking_budget": config.DOCUMENT_AGENT_THINKING_BUDGET
        },
        "file_system_agent": {
            "thinking_profile": AGENT_PROFILES.get("file_system_agent", "precision"),
            "max_tokens": config.FILE_SYSTEM_AGENT_MAX_TOKENS,
            "thinking_budget": config.FILE_SYSTEM_AGENT_THINKING_BUDGET
        },
        "browsing_agent": {
            "thinking_profile": AGENT_PROFILES.get("browsing_agent", "precision"),
            "max_tokens": config.BROWSING_AGENT_MAX_TOKENS,
            "thinking_budget": config.BROWSING_AGENT_THINKING_BUDGET
        },
        "visit_page": {
            "thinking_profile": AGENT_PROFILES.get("visit_page", "none"),
            "max_tokens": config.VISIT_PAGE_AGENT_MAX_TOKENS,
            "thinking_budget": config.VISIT_PAGE_AGENT_THINKING_BUDGET
        },
        "git_agent": {
            "thinking_profile": AGENT_PROFILES.get("git_agent", "precision"),
            "max_tokens": config.GIT_AGENT_MAX_TOKENS,
            "thinking_budget": config.GIT_AGENT_THINKING_BUDGET
        }
    })

@tools_bp.route('/config/agents/<agent_name>', methods=['PATCH'])
@admin_required
def update_agent_config(agent_name):
    from backend import config
    import backend.chat.agent_handler as agent_handler
    
    data, err = read_json_object()
    if err:
        return err
    
    # Update Thinking Profile
    if 'thinking_profile' in data:
        profile = data['thinking_profile']
        if profile in ['none', 'general', 'precision']:
            agent_handler.AGENT_PROFILES[agent_name] = profile
            logger.info(f"Updated {agent_name} thinking_profile to {profile}")
        else:
            return jsonify({"error": "Invalid thinking profile"}), 400
            
    # Update Max Tokens
    if 'max_tokens' in data:
        val = int(data['max_tokens'])
        if agent_name == "search_web": config.SEARCH_WEB_AGENT_MAX_TOKENS = val
        elif agent_name == "document_agent": config.DOCUMENT_AGENT_MAX_TOKENS = val
        elif agent_name == "file_system_agent": config.FILE_SYSTEM_AGENT_MAX_TOKENS = val
        elif agent_name == "browsing_agent": config.BROWSING_AGENT_MAX_TOKENS = val
        elif agent_name == "visit_page": config.VISIT_PAGE_AGENT_MAX_TOKENS = val
        elif agent_name == "git_agent": config.GIT_AGENT_MAX_TOKENS = val
        logger.info(f"Updated {agent_name} max_tokens to {val}")
        
    # Update Thinking Budget
    if 'thinking_budget' in data:
        val = int(data['thinking_budget'])
        if agent_name == "search_web": config.SEARCH_WEB_AGENT_THINKING_BUDGET = val
        elif agent_name == "document_agent": config.DOCUMENT_AGENT_THINKING_BUDGET = val
        elif agent_name == "file_system_agent": config.FILE_SYSTEM_AGENT_THINKING_BUDGET = val
        elif agent_name == "browsing_agent": config.BROWSING_AGENT_THINKING_BUDGET = val
        elif agent_name == "visit_page": config.VISIT_PAGE_AGENT_THINKING_BUDGET = val
        elif agent_name == "git_agent": config.GIT_AGENT_THINKING_BUDGET = val
        logger.info(f"Updated {agent_name} thinking_budget to {val}")
        
    return jsonify({"success": True})

# --- Browser Config Routes ---

@tools_bp.route('/config/browser', methods=['GET'])
@admin_required
def get_browser_config():
    from backend import config
    return jsonify({"stealth_level": config.BROWSER_STEALTH_LEVEL})

@tools_bp.route('/config/browser', methods=['PATCH'])
@admin_required
def update_browser_config():
    from backend import config
    data, err = read_json_object()
    if err:
        return err
    stealth_level = data.get('stealth_level')
    if stealth_level in ['minimal', 'advanced']:
        config.BROWSER_STEALTH_LEVEL = stealth_level
        logger.info(f"Updated global BROWSER_STEALTH_LEVEL to {stealth_level}")
        return jsonify({"success": True})
    return jsonify({"error": "Invalid stealth level"}), 400

# --- Browser Portal Proxy Routes ---

@tools_bp.route('/portal/vnc/', defaults={'path': 'vnc.html'})
@tools_bp.route('/portal/vnc/<path:path>')
def proxy_portal_vnc(path):
    """Reverse-proxy noVNC static files from the playwright_mcp container."""
    import httpx
    from backend.mcp_client import portal_vnc_auth_header

    auth = portal_vnc_auth_header()
    if not auth:
        log_event("portal_vnc_unconfigured", {})
        return jsonify({"error": "Browser portal is not configured"}), 503

    upstream_url = f"http://playwright_mcp:6080/{path}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(upstream_url, headers=auth)
            if resp.status_code == 401:
                log_event("portal_vnc_auth_failed", {"status": 401})
                return jsonify({"error": "Could not reach browser portal service"}), 502

            # Determine content type from upstream response
            content_type = resp.headers.get('content-type', 'application/octet-stream')
            
            return Response(
                resp.content,
                status=resp.status_code,
                content_type=content_type
            )
    except Exception as e:
        logger.error(f"Portal VNC proxy error: {e}")
        return jsonify({"error": "Could not reach browser portal service"}), 502

@tools_bp.route('/portal/init', methods=['POST'])
def proxy_portal_init():
    import httpx
    from backend.config import get_secret
    from backend.mcp_client import playwright_server_url

    base_url = playwright_server_url.replace('/sse', '')
    key = get_secret("PLAYWRIGHT_MCP_API_KEY", "")
    if not key:
        log_event("portal_init_unconfigured", {})
        return jsonify({"error": "Browser portal is not configured"}), 503

    try:
        with httpx.Client() as client:
            resp = client.post(f"{base_url}/portal/init", headers={"X-MCP-API-KEY": key}, timeout=60.0)
            if resp.status_code == 401:
                log_event("portal_init_auth_failed", {"status": 401})
                return jsonify({"error": "Browser portal authentication failed"}), 502
            if resp.status_code != 200:
                logger.error(f"Portal init proxy failed with status {resp.status_code}: {resp.text[:500]}")
                log_event("tools_portal_init_error", {"status_code": resp.status_code, "error": resp.text[:500]})
                return jsonify({"error": "Browser portal failed to start"}), 502
            data = resp.json()
            return jsonify(data)
    except httpx.HTTPError as e:
        logger.error(f"Portal init proxy could not reach the service: {e}")
        log_event("tools_portal_init_error", {"error": str(e)})
        return jsonify({"error": "Could not reach browser portal service"}), 502
    except Exception as e:
        logger.error(f"Portal init proxy exception: {e}")
        log_event("tools_portal_init_error", {"error": str(e)})
        return jsonify({"error": "Failed to start browser portal"}), 500


# --- Global System Settings Routes ---

@tools_bp.route('/config/settings', methods=['GET'])
@admin_required
def get_system_settings():
    from backend.database import db
    from backend import config
    settings = db.get_all_settings()
    # Ensure git_allowed_commands fallback is present
    if 'git_allowed_commands' not in settings:
        settings['git_allowed_commands'] = config.GIT_DEFAULT_ALLOWED_COMMANDS
    # Do not expose github_pat value directly, or expose only that a pat exists
    if 'github_pat' in settings and settings['github_pat']:
        settings['github_pat_configured'] = True
        # Do not send the raw token to the client for safety
        del settings['github_pat']
    else:
        settings['github_pat_configured'] = False
    
    # Expose known git subcommands and config-level permanently blocked commands
    settings['git_known_commands'] = config.GIT_ALL_KNOWN_COMMANDS

    # Provide defaults for code runner configuration settings
    settings['code_runner_timeout'] = settings.get('code_runner_timeout', config.CODE_RUNNER_DEFAULT_TIMEOUT)
    settings['code_runner_memory_limit'] = settings.get('code_runner_memory_limit', config.CODE_RUNNER_MEMORY_LIMIT)
    settings['code_runner_cpu_limit'] = settings.get('code_runner_cpu_limit', config.CODE_RUNNER_CPU_LIMIT)
    settings['code_runner_max_output_size'] = settings.get('code_runner_max_output_size', config.CODE_RUNNER_MAX_OUTPUT_SIZE)
    settings['code_runner_max_timeout'] = config.CODE_RUNNER_MAX_TIMEOUT   # read-only: the ceiling for code_runner_timeout

    return jsonify(settings)

@tools_bp.route('/config/settings', methods=['POST'])
@admin_required
def update_system_settings():
    from backend.database import db
    from backend import config
    data, err = read_json_object()
    if err:
        return err
    # Validate before writing anything, so a rejected request changes nothing.
    if 'code_runner_timeout' in data:
        value = data['code_runner_timeout']
        max_timeout = config.CODE_RUNNER_MAX_TIMEOUT
        is_int = isinstance(value, int) and not isinstance(value, bool)
        if not is_int and isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 9:
            value, is_int = int(value), True
        if not is_int or not 1 <= value <= max_timeout:
            return jsonify({"error": f"code_runner_timeout must be an integer from 1 to {max_timeout}"}), 400
        data['code_runner_timeout'] = value   # store the integer, whatever form it arrived in
    for key, val in data.items():
        if key == 'github_pat' and val == '__REDACTED__':
            # User submitted placeholder, ignore it
            continue
        if key == 'code_runner_max_timeout':
            # Read-only: shown to clients, never stored
            continue
        db.set_setting(key, val)
        logger.info(f"Updated system setting: {key}")
        
    return jsonify({"success": True})


@tools_bp.route('/code-execution/history/<chat_id>', methods=['GET'])
def get_execution_history(chat_id):
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    from backend.database import db
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    history = db.get_code_execution_history(chat_id, limit=limit, offset=offset)
    return jsonify(history)


@tools_bp.route('/code-execution/run-file', methods=['POST'])
async def api_run_file():
    """Direct file execution (user-triggered, not AI-triggered)."""
    import uuid
    from backend.tools.implementations.code_executor import run_file, resolve_run_target
    data, err = read_json_object(required=False)
    if err:
        return err
    path = data.get("path")
    chat_id = data.get("chat_id")
    stdin = data.get("stdin", "")
    args = data.get("args", [])
    sql_target = data.get("sql_target", "sqlite")
    
    if not path or not chat_id:
        return jsonify({"error": "Missing path or chat_id"}), 400
    if not isinstance(chat_id, str):
        return jsonify({"error": "Invalid chat_id"}), 400
    denied = require_chat_owner(chat_id)
    if denied:
        return denied

    try:
        resolve_run_target(chat_id, path)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404
    except ValueError:
        return jsonify({"error": "Invalid file path"}), 400
    except Exception as e:
        logger.error(f"Error resolving file for direct run: {e}", exc_info=True)
        log_event("tools_run_file_error", {"chat_id": chat_id, "path": path[:200], "error": str(e)})
        return jsonify({"error": "Failed to run file"}), 500

    try:
        result = await run_file(
            path=path,
            stdin=stdin,
            args=args,
            sql_target=sql_target,
            chat_id=chat_id,
            tool_call_id=f"direct_{uuid.uuid4().hex[:12]}"
        )
        return jsonify({"result": result})
    except Exception as e:
        logger.error(f"Error running file directly: {e}", exc_info=True)
        log_event("tools_run_file_error", {"chat_id": chat_id, "path": path[:200], "error": str(e)})
        return jsonify({"error": "Failed to run file"}), 500


