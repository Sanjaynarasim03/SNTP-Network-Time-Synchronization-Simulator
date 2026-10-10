"""
Flask Web Dashboard for SNTP Simulator.

Provides interactive REST APIs and serves the presentation-ready frontend UI.
"""

import os
from flask import Flask, render_template, jsonify, request, Response
from simulator.simulation_manager import SimulationManager

# Initialize Flask app pointing to dashboard directories
current_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(current_dir, "templates"),
    static_folder=os.path.join(current_dir, "static"),
)

# Shared Simulation Manager instance
sim_manager = SimulationManager(server_port=1123)


@app.route("/")
def index():
    """Serves the main single-page dashboard."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    """Returns real-time status of all simulated clients and the SNTP server."""
    return jsonify(sim_manager.get_all_summaries())


@app.route("/api/start", methods=["POST"])
def start_sim():
    """Starts background periodic polling for all clients."""
    sim_manager.start_simulation()
    return jsonify({"success": True, "is_running": sim_manager.is_running})


@app.route("/api/stop", methods=["POST"])
def stop_sim():
    """Stops background periodic polling."""
    sim_manager.stop_simulation()
    return jsonify({"success": True, "is_running": sim_manager.is_running})


@app.route("/api/reset", methods=["POST"])
def reset_sim():
    """Resets all clients and virtual clocks to initial conditions."""
    sim_manager.reset_all()
    return jsonify({"success": True, "data": sim_manager.get_all_summaries()})


@app.route("/api/sync", methods=["POST"])
def sync_now():
    """Triggers an instantaneous sync round."""
    data = request.get_json(silent=True) or {}
    client_id = data.get("client_id")
    if client_id and client_id in sim_manager.clients:
        res = sim_manager.sync_client_once(client_id)
        return jsonify({"success": True, "client": res})
    else:
        results = sim_manager.sync_all_once()
        return jsonify({"success": True, "results": results})


@app.route("/api/client/<client_id>/update", methods=["POST"])
def update_client(client_id):
    """Updates network and clock parameters for a specific client."""
    params = request.get_json(silent=True) or {}
    sim_manager.update_client_params(client_id, params)
    client = sim_manager.clients.get(client_id)
    if client:
        return jsonify({"success": True, "client": client.get_summary()})
    return jsonify({"success": False, "error": "Client not found"}), 404


@app.route("/api/client/<client_id>/history", methods=["GET"])
def client_history(client_id):
    """Fetches the sync transaction history list for a client."""
    history = sim_manager.get_client_history(client_id)
    return jsonify({"client_id": client_id, "history": history})


@app.route("/api/experiment/<experiment_id>", methods=["POST"])
def run_experiment(experiment_id):
    """Executes a preset scenario experiment and returns comparative results."""
    result = sim_manager.apply_experiment(experiment_id)
    return jsonify(result)


@app.route("/api/packet-inspect", methods=["GET"])
def packet_inspect():
    """Fetches the most recent raw packet analysis for display in the Packet Inspector."""
    client_id = request.args.get("client_id", "client_a")
    client = sim_manager.clients.get(client_id)
    if client and client.last_sync_record and client.last_sync_record.packet_inspect:
        return jsonify({
            "has_data": True,
            "client_id": client_id,
            "record": client.last_sync_record.packet_inspect,
            "raw_hex": client.last_sync_record.raw_packet_hex,
            "status": client.last_sync_record.status,
            "t1": client.last_sync_record.t1,
            "t2": client.last_sync_record.t2,
            "t3": client.last_sync_record.t3,
            "t4": client.last_sync_record.t4,
            "offset_ms": client.last_sync_record.offset_ms,
            "delay_ms": client.last_sync_record.delay_ms,
        })

    # Fallback to a synthetic sample packet if no real request has executed yet
    from server.packet import SNTPPacket
    import time
    now = time.time()
    sample = SNTPPacket(
        li=0, vn=4, mode=4, stratum=1, poll=4, precision=-20,
        ref_id=b"LOCL", ref_timestamp=now - 5, orig_timestamp=now - 0.05,
        recv_timestamp=now - 0.03, tx_timestamp=now - 0.02
    )
    return jsonify({
        "has_data": False,
        "sample": True,
        "record": sample.to_inspect_dict(),
        "raw_hex": sample.pack().hex().upper(),
    })


@app.route("/api/export-csv", methods=["GET"])
def export_csv():
    """Streams CSV log file download."""
    csv_data = sim_manager.export_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sntp_simulation_logs.csv"}
    )


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
