# -*- coding: UTF-8 -*-
import json
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from utils.smtp import *
from utils.pop3 import *

app = Flask(__name__)
CORS(app, supports_credentials=True)

# @app.before_request
# def before_request():
#     current_user = get_jwt_identity()
#     print(current_user)
#     if current_user is None:
#         return jsonify({"error": "JWT authentication is required !!!"}), 401

@app.route('/', methods=[ 'GET', 'POST' ])
def index():
    auth = request.authorization
    print(auth)

    return render_template('index.html')

@app.route('/pop3', methods=[ 'POST' ])
def pop3():
    authorization = request.authorization
    # print(authorization)

    auth = {}
    if request.method == 'POST':
        if request.json is not None:
            if is_json(request.json):
                auth = request.json.get('auth')
        if auth is None or str(auth) == '{}':
            data = open('data.json', 'r')
            info = json.load(data)
            auth = info['auth']

    print(auth)
    result = {}
    result['result'] = get_pop3(auth)
    return jsonify(result), 200

@app.route('/send', methods=[ 'POST' ])
def send():
    authorization = request.authorization
    # print(authorization)

    auth = {}
    if request.method == 'POST':
        if request.json is not None:
            if is_json(request.json):
                auth = request.json.get('auth')
                mails = request.json.get('mails')
        if auth is None or str(auth) == '{}':
            data = open('data.json', 'r')
            info = json.load(data)
            auth = info['auth']

    result = {}
    result['result'] = sendMail(auth, mails)
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8082)