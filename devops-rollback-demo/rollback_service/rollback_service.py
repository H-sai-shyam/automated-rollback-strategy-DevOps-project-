from flask import Flask, request, jsonify
import subprocess, json, os, threading, shutil

app = Flask(__name__)

# configure these
COMPOSE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STABLE_IMAGE = "app:v1"
NEXT_IMAGE = "app:v2"

lock = threading.Lock()
current = {"image": NEXT_IMAGE}  # assume we start with v2 deployed

def find_compose_cmd():
    # prefer docker-compose binary, fallback to `docker compose`
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    # check if `docker` exists and supports `compose`
    if shutil.which("docker"):
        # we'll use "docker compose" as a single command list
        return ["docker", "compose"]
    return None

def run_compose_with_image(image):
    env = os.environ.copy()
    env['APP_IMAGE'] = image
    compose_cmd = find_compose_cmd()
    if not compose_cmd:
        return 127, "", "docker-compose (or docker) not found in PATH"

    # build the full command list
    cmd = compose_cmd + ["-f", os.path.join(COMPOSE_DIR,'docker-compose.yml'), "up", "-d", "--no-deps", "--force-recreate", "app"]
    print(f"[rollback] Running: APP_IMAGE={image} {' '.join(cmd)} (cwd={COMPOSE_DIR})")
    proc = subprocess.run(cmd, cwd=COMPOSE_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr

@app.route('/', methods=['GET'])
def index():
    return jsonify({"msg":"rollback service running", "current_image": current['image']}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        payload = request.get_json(force=True)
    except Exception as e:
        print("[webhook] Invalid JSON payload:", e)
        return jsonify({"error":"invalid json", "detail": str(e)}), 400

    alerts = payload.get('alerts', [])
    firing = [a for a in alerts if a.get('status') == 'firing']
    if not firing:
        print("[webhook] Received payload but no firing alerts")
        return jsonify({"msg":"no firing alerts"}), 200

    severities = [a.get('labels', {}).get('severity','') for a in firing]
    print("[webhook] Received firing alerts with severities:", severities)

    if 'critical' in severities or 'warning' in severities:
        with lock:
            if current['image'] == STABLE_IMAGE:
                print("[webhook] Already on stable image:", STABLE_IMAGE)
                return jsonify({"msg":"already stable"}), 200
            code, out, err = run_compose_with_image(STABLE_IMAGE)
            print("[webhook] compose exit:", code)
            if out:
                print("[webhook] compose stdout:", out)
            if err:
                print("[webhook] compose stderr:", err)
            if code == 0:
                current['image'] = STABLE_IMAGE
                return jsonify({"msg":"rolled back to "+STABLE_IMAGE, "out":out}), 200
            else:
                return jsonify({"error":"compose failed","out":out,"err":err}), 500

    print("[webhook] No action required for severities:", severities)
    return jsonify({"msg":"no action taken"}), 200

if __name__ == '__main__':
    # debug = False for demo (but can set to True while testing)
    app.run(host='0.0.0.0', port=5001)
