import azure.functions as func
import requests
import datetime
import json
import logging
import os
import uuid
from azure.cosmos import CosmosClient

app = func.FunctionApp()

# Initialize Cosmos DB client
cosmos_connection_string = os.environ.get("AzureCosmosDBConnectionString")
database_name = os.environ.get("DatabaseName")
player_container_name = os.environ.get("PlayerContainerName")
prompt_container_name = os.environ.get("PromptContainerName")

# Create Cosmos client
cosmos_client = CosmosClient.from_connection_string(cosmos_connection_string)
database = cosmos_client.get_database_client(database_name)
player_container = database.get_container_client(player_container_name)
prompt_container = database.get_container_client(prompt_container_name)

@app.function_name(name="player_register")
@app.route(route="player/register", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def player_register(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        username = req_body["username"]
        password = req_body["password"]

        # Validate username length
        if len(username) < 5 or len(username) > 12:
            response = {
                "result": False,
                "msg": "Username less than 5 characters or more than 12 characters"
            }
            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json")

        # Validate password length
        if len(password) < 8 or len(password) > 12:
            response = {
                "result": False,
                "msg": "Password less than 8 characters or more than 12 characters"
            }
            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json")

        # Check if username already exists
        query = f"SELECT * FROM c WHERE c.username = '{username}'"
        existing_players = list(player_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if len(existing_players) > 0:
            response = {
                "result": False,
                "msg": "Username already exists"
            }
            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json")

        # Create new player document with auto-generated ID
        new_player = {
            "id": str(uuid.uuid4()),  # Auto-generate unique ID
            "username": username,
            "password": password,
            "games_played": 0,
            "total_score": 0
        }

        # Insert into Cosmos DB
        player_container.create_item(body=new_player)

        response = {
            "result": True,
            "msg": "OK"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json")

    except Exception as e:
        logging.error(f"Error in player_register: {str(e)}")
        response = {
            "result": False,
            "msg": f"Error: {str(e)}"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=500)


@app.function_name(name="player_login")
@app.route(route="player/login", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def player_login(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        username = req_body["username"]
        password = req_body["password"]

        query = f"SELECT * FROM c WHERE c.username = '{username}'"

        # Convert to list to check results
        players = list(player_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        # Check if player exists and password matches
        if len(players) == 1 and players[0]["password"] == password:
            response = {
                "result": True,
                "msg": "OK"
            }
        else:
            # Either player doesn't exist OR password is wrong
            response = {
                "result": False,
                "msg": "Username or password incorrect"
            }

        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json")

    except Exception as e:
        logging.error(f"Error in player_login: {str(e)}")
        response = {
            "result": False,
            "msg": f"Error: {str(e)}"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=500)

@app.function_name(name="player_update")
@app.route(route="player/update", methods=["PUT"], auth_level=func.AuthLevel.FUNCTION)
def player_update(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        username = req_body["username"]
        add_to_games_played = req_body["add_to_games_played"]
        add_to_score = req_body["add_to_score"]

        query = f"SELECT * FROM c WHERE c.username = '{username}'"

        players = list(player_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if len(players) == 0:
            response = {
                "result": False,
                "msg": "Player does not exist"
            }
            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json")

        # Player exists, update the values
        player = players[0]
        player["games_played"] += add_to_games_played
        player["total_score"] += add_to_score

        # Replace the item in Cosmos DB
        player_container.replace_item(item=player, body=player)

        response = {
            "result": True,
            "msg": "OK"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json")

    except Exception as e:
        logging.error(f"Error in player_update: {str(e)}")
        response = {
            "result": False,
            "msg": f"Error: {str(e)}"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=500)


@app.function_name(name="prompt_create")
@app.route(route="prompt/create", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def prompt_create(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        text = req_body["text"]
        username = req_body["username"]
        tags = req_body["tags"]

        # Check text length
        if len(text) < 20 or len(text) > 120:
            response = {
                "result": False,
                "msg": "Prompt less than 20 characters or more than 120 characters"
            }
            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json")

        # Check if player exists
        query = f"SELECT * FROM c WHERE c.username = '{username}'"
        players = list(player_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        if len(players) == 0:
            response = {
                "result": False,
                "msg": "Player does not exist"
            }
            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json")


        translation_endpoint = os.environ.get("TranslationEndpoint")
        translation_key = os.environ.get("TranslationKey")
        translation_region = os.environ.get("TranslationRegion", "italynorth")  # Default to italynorth

        # Detect language
        detect_url = f"{translation_endpoint}/detect?api-version=3.0"
        detect_headers = {
            'Ocp-Apim-Subscription-Key': translation_key,
            'Ocp-Apim-Subscription-Region': translation_region,
            'Content-type': 'application/json'
        }
        detect_body = [{'text': text}]

        detect_response = requests.post(detect_url, headers=detect_headers, json=detect_body)
        detect_result = detect_response.json()

        detected_language = detect_result[0]['language']
        confidence = detect_result[0]['score']

        # Check language confidence
        if confidence < 0.2:
            response = {
                "result": False,
                "msg": "Unsupported language"
            }
            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json")

        # Supported languages: English (en), Welsh (cy), Spanish (es), Tamil (ta), Chinese Simplified (zh-Hans), Arabic (ar)
        supported_languages = ['en', 'cy', 'es', 'ta', 'zh-Hans', 'ar']


        texts = [{"text": text, "language": detected_language}]

        # Translate to all other supported languages
        for target_lang in supported_languages:
            if target_lang != detected_language:
                translate_url = f"{translation_endpoint}/translate?api-version=3.0&from={detected_language}&to={target_lang}"
                translate_headers = {
                    'Ocp-Apim-Subscription-Key': translation_key,
                    'Ocp-Apim-Subscription-Region': translation_region,
                    'Content-type': 'application/json'
                }
                translate_body = [{'text': text}]

                translate_response = requests.post(translate_url, headers=translate_headers, json=translate_body)
                translate_result = translate_response.json()

                translated_text = translate_result[0]['translations'][0]['text']
                texts.append({"text": translated_text, "language": target_lang})


        unique_tags = list(dict.fromkeys(tags))

        prompt_doc = {
            "id": str(uuid.uuid4()),  # Auto-generate unique ID
            "username": username,
            "texts": texts,
            "tags": unique_tags
        }

       
        prompt_container.create_item(body=prompt_doc)

        response = {
            "result": True,
            "msg": "OK"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json")

    except Exception as e:
        logging.error(f"Error in prompt_create: {str(e)}")
        response = {
            "result": False,
            "msg": f"Error: {str(e)}"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=500)



@app.function_name(name="prompt_moderate")
@app.route(route="prompt/moderate", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def prompt_moderate(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        prompt_ids = req_body["prompt-ids"]

        content_safety_endpoint = os.environ.get("ContentSafetyEndpoint")
        content_safety_key = os.environ.get("ContentSafetyKey")

        results = []

        for prompt_id in prompt_ids:
            # Query for the prompt by ID
            query = f"SELECT * FROM c WHERE c.id = '{prompt_id}'"
            prompts = list(prompt_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            # If prompt doesn't exist, skip it
            if len(prompts) == 0:
                continue

            prompt = prompts[0]

            # Get the English text from the prompt
            english_text = None
            for text_obj in prompt["texts"]:
                if text_obj["language"] == "en":
                    english_text = text_obj["text"]
                    break

            if not english_text:
                continue

            # Call Content Safety API
            moderate_url = f"{content_safety_endpoint}contentsafety/text:analyze?api-version=2023-10-01"
            moderate_headers = {
                'Ocp-Apim-Subscription-Key': content_safety_key,
                'Content-Type': 'application/json'
            }
            moderate_body = {
                "text": english_text
            }

            moderate_response = requests.post(moderate_url, headers=moderate_headers, json=moderate_body)
            moderate_result = moderate_response.json()
            
            # Extract severity scores from the 4 categories
            categories = moderate_result.get("categoriesAnalysis", [])
            severities = [cat["severity"] for cat in categories]

            average_severity = sum(severities) / len(severities) if severities else 0

            outcome = average_severity > 2

            # Round to 2 decimal places for consistency
            average_severity = round(average_severity, 2)

            results.append({
                "prompt-id": prompt_id,
                "outcome": outcome,
                "average_severity": average_severity
            })

        return func.HttpResponse(
            json.dumps(results),
            mimetype="application/json")

    except Exception as e:
        logging.error(f"Error in prompt_moderate: {str(e)}")
        response = {
            "result": False,
            "msg": f"Error: {str(e)}"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=500)


@app.function_name(name="prompt_delete")
@app.route(route="prompt/delete", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def prompt_delete(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        player = req_body["player"]

        # Query for all prompts by this player
        query = f"SELECT * FROM c WHERE c.username = '{player}'"
        prompts_to_delete = list(prompt_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        # Delete each prompt
        deleted_count = 0
        for prompt in prompts_to_delete:
            prompt_container.delete_item(
                item=prompt["id"],
                partition_key=prompt["username"]
            )
            deleted_count += 1

        response = {
            "result": True,
            "msg": f"{deleted_count} prompts deleted"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json")

    except Exception as e:
        logging.error(f"Error in prompt_delete: {str(e)}")
        response = {
            "result": False,
            "msg": f"Error: {str(e)}"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=500)


@app.function_name(name="utils_get")
@app.route(route="utils/get", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def utils_get(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        players = req_body["players"]
        tag_list = req_body["tag_list"]

        # Convert tag_list to lowercase for case-insensitive comparison
        tag_list_lower = [tag.lower() for tag in tag_list]

        results = []

        # Query for all prompts by the specified players
        for player in players:
            query = f"SELECT * FROM c WHERE c.username = '{player}'"
            prompts = list(prompt_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            # Filter prompts that have at least one matching tag
            for prompt in prompts:
                prompt_tags_lower = [tag.lower() for tag in prompt.get("tags", [])]
                if any(tag in tag_list_lower for tag in prompt_tags_lower):
                    results.append(prompt)

        return func.HttpResponse(
            json.dumps(results),
            mimetype="application/json")

    except Exception as e:
        logging.error(f"Error in utils_get: {str(e)}")
        response = {
            "result": False,
            "msg": f"Error: {str(e)}"
        }
        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=500)


@app.function_name(name="utils_welcome")
@app.cosmos_db_trigger(arg_name="documents",
                       database_name=database_name,
                       container_name=player_container_name,
                       connection="AzureCosmosDBConnectionString",
                       lease_container_name="leases",
                       create_lease_container_if_not_exists=True)
def utils_welcome(documents: func.DocumentList) -> None:
    try:
        translation_endpoint = os.environ.get("TranslationEndpoint")
        translation_key = os.environ.get("TranslationKey")
        translation_region = os.environ.get("TranslationRegion", "italynorth")

        for doc in documents:
            # Check if this is a new player registration (games_played == 0 and total_score == 0)
            if doc.get("games_played") == 0 and doc.get("total_score") == 0:
                username = doc.get("username")

                # Check if a welcome prompt already exists for this user
                try:
                    welcome_check_query = f"SELECT * FROM c WHERE c.username = '{username}'"
                    existing_prompts = list(prompt_container.query_items(
                        query=welcome_check_query,
                        enable_cross_partition_query=True
                    ))

                    # Filter to check for welcome messages (empty tags and contains welcome text)
                    existing_welcome = []
                    for p in existing_prompts:
                        if len(p.get('tags', [])) == 0:
                            for text_obj in p.get('texts', []):
                                if 'welcome to comp3207' in text_obj.get('text', '').lower():
                                    existing_welcome.append(p)
                                    break

                    # Skip if welcome already exists
                    if len(existing_welcome) > 0:
                        logging.info(f"Welcome prompt already exists for user: {username}, skipping creation")
                        continue
                except Exception as check_error:
                    logging.warning(f"Error checking for existing welcome prompt: {str(check_error)}")
                    # Continue to create welcome even if check fails

                welcome_text = f"Welcome to COMP3207, {username}"

                supported_languages = ['en', 'cy', 'es', 'ta', 'zh-Hans', 'ar']

                # Start with English
                texts = [{"text": welcome_text, "language": "en"}]

                # Translate to all other supported languages
                for target_lang in supported_languages:
                    if target_lang != "en":
                        translate_url = f"{translation_endpoint}/translate?api-version=3.0&from=en&to={target_lang}"
                        translate_headers = {
                            'Ocp-Apim-Subscription-Key': translation_key,
                            'Ocp-Apim-Subscription-Region': translation_region,
                            'Content-type': 'application/json'
                        }
                        translate_body = [{'text': welcome_text}]

                        translate_response = requests.post(translate_url, headers=translate_headers, json=translate_body)
                        translate_result = translate_response.json()

                        translated_text = translate_result[0]['translations'][0]['text']
                        texts.append({"text": translated_text, "language": target_lang})

                welcome_prompt = {
                    "id": str(uuid.uuid4()),
                    "username": username,
                    "texts": texts,
                    "tags": []
                }

                prompt_container.create_item(body=welcome_prompt,)


                logging.info(f"Welcome prompt created for user: {username}")

    except Exception as e:
        logging.error(f"Error in utils_welcome: {str(e)}")


