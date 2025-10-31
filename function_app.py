import azure.functions as func
import requests
import datetime
import json
import logging

app = func.FunctionApp()

@app.function_name(name="player_register")
@app.route(route="player/register", methods=["POST"])
def player_register(req: func.HttpRequest) -> func.HTTPResponse:
    json = req.get_json() 
    username = json["username"]
    password = json["password"]

    if len(username) < 5 or len(username) > 12:
        response = {
            "result":"false",
            "msg":"Username less than 5 characters or more than 12 characters"
        }
        return func.HttpResponse(
            json.dumps(response), 
            mimetype="application/json")

    if len(password) < 8 or len(password) > 12:
        response = {
            "result":"false",
            "msg":"Password less than 8 characters or more than 12 characters"
        }
        return func.HttpResponse(
            json.dumps(response), 
            mimetype="application/json")
    
    

