

from flask import jsonify

def success(message="Success", data=None, status=200):
    return jsonify({
        "success": True,
        "status": status,
        "message": message,
        "data": data
    }), status


def error(message="Error", status=400, data=None):
    return jsonify({
        "success": False,
        "status": status,
        "message": message,
        "data": data
    }), status
