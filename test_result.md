#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
## user_problem_statement: >
  Faceless AI Reels app (GhostReelsAlpha). Two items this session:
  (1) P0 bug — AI-image reel generation hangs at 82% on production. Root cause: FFmpeg
  Ken Burns zoompan supersampled to scale=1620:2880 which peaked at ~3GB RAM and got
  OOM-killed on the memory-limited prod pod. Fixed by reducing to scale=1350:2400
  (peak RAM now ~188MB, render ~14s). Confirmed via standalone repro (backend/tests/test_render_82.py).
  (2) P1 feature — extend the "AI script review/edit before spending credits" step
  (already in the single-reel flow) to the Series and Batch generation flows.

## backend:
##   - task: "AI-image render OOM fix (82% hang)"
##     implemented: true
##     working: true
##     file: "/app/backend/pipeline.py (render_video_images)"
##     status_history:
##       - agent: "main"
##         comment: "scale=1620:2880 -> 1350:2400. Repro proves peak RAM 3039MB -> 188MB; render OK in ~14s even with 4096x6144 images. Self-tested."
##   - task: "Series episode script preview + reviewed-script build"
##     implemented: true
##     working: true
##     file: "/app/backend/server.py"
##     needs_retesting: true
##     status_history:
##       - agent: "main"
##         comment: "New POST /api/series/{id}/episode/script (drafts continuity script, no quota consume). EpisodeRequest gains optional script; create_series_episode stores it so pipeline skips scripting. Mock e2e verified: reviewed script persisted, series_id set."
##   - task: "Batch script preview + reviewed-script build"
##     implemented: true
##     working: true
##     file: "/app/backend/server.py"
##     needs_retesting: true
##     status_history:
##       - agent: "main"
##         comment: "New POST /api/reels/batch/scripts (drafts one script per topic in parallel, gated to BYOK/subscription/admin). BatchReelRequest gains optional scripts[]; create_reels_batch pairs script to topic. Mock e2e verified: edited script persisted per reel."

## frontend:
##   - task: "Series review step UI"
##     implemented: true
##     working: "NA"
##     file: "/app/frontend/app/series/[id].tsx"
##     needs_retesting: true
##     status_history:
##       - agent: "main"
##         comment: "Added Write episode script (episode-write-script-button) -> editable episode-script-input -> Generate episode (disabled until script drafted)."
##   - task: "Batch review step UI"
##     implemented: true
##     working: "NA"
##     file: "/app/frontend/app/batch.tsx"
##     needs_retesting: true
##     status_history:
##       - agent: "main"
##         comment: "Two-step CTA: Write scripts (batch-write-scripts-button) -> per-topic editable batch-script-input-{i} -> Generate reels. Editing topics/length clears drafts."

## metadata:
##   created_by: "main_agent"
##   version: "1.1"
##   test_sequence: 1

## test_plan:
##   current_focus:
##     - "Series episode script preview + reviewed-script build"
##     - "Batch script preview + reviewed-script build"
##     - "Series review step UI"
##     - "Batch review step UI"
##   stuck_tasks: []
##   test_all: false
##   test_priority: "high_first"

## agent_communication:
##   - agent: "main"
##     message: >
##       Please test the NEW AI-script-review flows end-to-end. Admin creds (unlimited, bypasses quota
##       + gates batch): russngina@gmail.com / 1123581321$$ (see /app/memory/test_credentials.md).
##       REELS_MOCK=0 (real generation) and the Universal Key budget was topped up by the user, so real
##       generation should work; if it hits the budget cap you may set REELS_MOCK=1 in /app/backend/.env
##       (restart backend) to test the flows credit-free, then set it back to 0.
##       Backend to verify: POST /api/reels/batch/scripts (returns one script per topic; >12 or empty -> 400;
##       non-BYOK/non-sub/non-admin -> 402), POST /api/reels/batch with scripts[] (reviewed script persists
##       on each reel doc), POST /api/series/{id}/episode/script (returns continuity draft + episode_number),
##       POST /api/series/{id}/episode with script (persists reviewed script, series_id set, scripting skipped).
##       Frontend to verify: Series detail -> Write episode script -> edit -> Generate episode; Batch -> Write
##       scripts -> edit each -> Generate reels; editing topics clears drafts. Single-reel flow unchanged.

## ---- Session 2: BYOK error attribution + AI-engine toggle ----
## backend:
##   - task: "Accurate BYOK error attribution (OwnKeyError)"
##     implemented: true
##     working: true
##     file: "/app/backend/pipeline.py, /app/backend/server.py (classify_error)"
##     needs_retesting: true
##     status_history:
##       - agent: "main"
##         comment: "pipeline wraps own-key OpenAI/Google failures in OwnKeyError(provider). classify_error now returns a message naming the user's OWN key (OpenAI vs Google) for auth/quota errors instead of the misleading 'top up Universal Key'. Direct test: bad own OpenAI key -> 402 'Your OpenAI key was rejected... or switch to Built-in credits'."
##   - task: "AI engine toggle (key_mode own|builtin)"
##     implemented: true
##     working: true
##     file: "/app/backend/server.py (user_keys/saved_keys/public_user/update_settings)"
##     needs_retesting: true
##     status_history:
##       - agent: "main"
##         comment: "users.key_mode default 'own'. user_keys() returns ('','') when 'builtin' so pipeline uses Universal key; saved_keys() always decrypts for masking. PUT /settings accepts key_mode. Direct test: builtin mode -> /script generated a real script via Universal key (keys ignored)."
## frontend:
##   - task: "AI engine toggle UI in Settings"
##     implemented: true
##     working: "NA"
##     file: "/app/frontend/app/settings.tsx"
##     needs_retesting: true
##     status_history:
##       - agent: "main"
##         comment: "Segmented control (key-mode-own / key-mode-builtin) at top of AI KEYS. Persists via updateSettings + refreshAuth, optimistic. Note box explains AI-image reels need BOTH keys. Renders correctly (screenshot, admin login)."
## agent_communication:
##   - agent: "main"
##     message: >
##       Session 2 test focus: (1) POST /settings with key_mode 'own'/'builtin' persists and GET /settings
##       reflects it; in 'builtin' mode a saved key is IGNORED for generation (user_keys empty) but still
##       shown as set/masked. (2) A generation failure using the user's OWN key returns error_code 'key'
##       with a message naming OpenAI or Google (NOT the Universal-key wording). Use a throwaway account with
##       a bogus key 'sk-invalidkey-0000' and POST /script -> expect 402 + 'Your OpenAI key was rejected'.
##       (3) Frontend Settings: tap key-mode-builtin then key-mode-own; toggle persists across reload;
##       note box visible. Admin creds russngina@gmail.com / 1123581321$$. REELS_MOCK=0.
