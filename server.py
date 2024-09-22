from flask import Flask, request, jsonify, redirect, url_for, render_template, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from functools import wraps
import datetime
import os
import random
from datetime import datetime
app = Flask(__name__)

client = MongoClient('mongodb://localhost:27017/')
db = client['AutoSale']
users_collection = db['Keys']
clients_collection = db['clients']
dealers_collection = db['dealers']
contracts_collection = db['contracts'] 
cars_collection = db['cars']

UPLOAD_FOLDER = './static/images/cars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def get_collection_info(documents, name):
    fields = {}
    for doc in documents:
        for key in doc.keys():
            fields.update({key: str(type(doc[key]).__name__)})
            if str(type(doc[key]).__name__) == "ObjectId":
                doc[key] = str(doc[key])
    response = {
        "collection_name": name,
        "fields": fields,
        "documents": documents
    }

    return response


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_current_user():
    username = request.cookies.get('username')
    if not username:
        return None
    user = users_collection.find_one({"login": username})
    return user


def role_required(*roles):
    def decorator(f):
        @ wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if user and user['role'] in roles:
                return f(*args, **kwargs)
            else:
                return jsonify({"error": "Unauthorized access"}), 403
        return decorated_function
    return decorator


@app.route('/api/isdealer', methods=["GET"])
def isDealer():
    user = get_current_user()
    if user is None:
        return False
    dealer = dealers_collection.find_one({"user_id": user["_id"]})
    return {"dealer": dealer != None}


@ app.route('/', methods=['GET'])
def get_index_page():
    return render_template(
        "index.html"
    )


@ app.route('/collections', methods=['GET'])
def get_collections_page():
    return render_template(
        "collections.html"
    )


@ app.route('/users', methods=['GET'])
@ role_required("owner", "admin")
def get_users_page():
    return render_template(
        "users.html"
    )


@ app.route('/profile', methods=['GET'])
def get_profile_page():
    return render_template(
        "profile.html"
    )


@ app.route('/statistics', methods=['GET'])
def get_statistics_page():
    return render_template(
        "statistics.html"
    )


@ app.route('/api/users', methods=['GET'])
@ role_required("owner", "admin")
def get_users():
    users = list(users_collection.find({}))
    for user in users:
        user['_id'] = str(user['_id'])
    return jsonify(users)


@ app.route('/api/password/<login>', methods=['GET'])
def get_users_password(login):
    user = users_collection.find_one({"login": login})
    return jsonify(user['password'])


@ app.route('/api/users/<id>', methods=['DELETE'])
@ role_required("owner", "admin")
def delete_user(id):
    users_collection.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('get_users'))


@ app.route('/api/users/<user_id>/role', methods=['PUT'])
@ role_required("admin", "owner")
def update_user_role(user_id):
    if 'username' not in request.cookies:
        return jsonify({"message": "Unauthorized access"}), 401

    current_user = users_collection.find_one(
        {"login": request.cookies['username']})
    if not current_user:
        return jsonify({"message": "Forbidden"}), 403

    data = request.json
    new_role = data.get('role')

    valid_roles = ['user', 'operator', 'admin', 'owner']
    if new_role not in valid_roles:
        return jsonify({"message": "Invalid role"}), 400

    users_collection.update_one({"_id": ObjectId(user_id)}, {
                                "$set": {"role": new_role}})

    return jsonify({"message": "Роль оновлено"}), 200


@ app.route('/authorize/login', methods=['POST', 'GET'])
def login():
    login = request.form['login']
    password = request.form['password']
    user = users_collection.find_one({"login": login, "password": password})
    if not user:
        return jsonify({"error": "Неправильний логін або пароль"}), 401
    response = jsonify({"login": user['login'], "role": user['role']})
    response.set_cookie('user', user['login'])
    return response, 200


@ app.route('/authorize/signup', methods=['POST'])
def signup():
    login = request.form.get("login")
    password = request.form.get("password")

    who = request.form.get("who")
    name = request.form.get("name")
    city = request.form.get("city")
    address = request.form.get("address")
    phone = request.form.get("phone")
    photo = request.files.get("photo")

    existing_user = users_collection.find_one({"login": login})
    if existing_user:
        return jsonify({"success": False, "message": "Користувач з таким логіном вже існує."}), 409

    role = "user"
    if users_collection.count_documents({"role": "owner"}) == 0:
        role = "owner"

    users_collection.insert_one({
        "login": login,
        "password": password,
        "role": role
    })
    current_user = users_collection.find_one({"login": login})
    if who == "dealer":
        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            photo_path = os.path.join('./static/images/dealers', filename)
            os.makedirs('./static/images/dealers', exist_ok=True)
            photo.save(photo_path)
        else:
            return jsonify({"success": False, "message": "Invalid photo format."}), 400
        dealers_collection.insert_one({
            "user_id": current_user["_id"],
            "name": name,
            "photo": filename,
            "address": address,
        }
        )
    else:
        clients_collection.insert_one({
            "user_id": current_user["_id"],
            "name": name,
            "city": city,
            "address": address,
            "phone": phone
        }
        )
    return jsonify({"success": True, "login": login, "role": role})


@ app.route('/api/cars', methods=['GET'])
def get_cars():
    cars = []
    user = get_current_user()
    if (user != None):
        if (isDealer()["dealer"]):
            dealer = dealers_collection.find_one({"user_id": user["_id"]})
            cars = list(cars_collection.find({"dealer_id": dealer["_id"]}))
        else:
            cars = list((cars_collection.find({"sold": False})))
    for car in cars:
        car['_id'] = str(car['_id'])
        car['dealer_id'] = str(car['dealer_id'])
    return jsonify(cars)


@ app.route('/api/cars', methods=['POST'])
def add_car():
    brand = request.form['brand']
    model = request.form['model']
    year = int(request.form['year'])
    mileage = int(request.form['mileage'])
    price = float(request.form['price'])
    notes = request.form['notes']
    color = request.form['color']
    photo = request.files['photo']
    dealer_id = dealers_collection.find_one(
        {"user_id": get_current_user()['_id']})["_id"]
    if 'photo' not in request.files:
        return jsonify({'error': 'Не завантажено фото'}), 400

    if photo.filename == '':
        return jsonify({'error': 'Не завантажено фото'}), 400

    file_path = os.path.join(UPLOAD_FOLDER, photo.filename)

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    photo.save(file_path)
    car_data = {
        'brand': brand,
        'model': model,
        'color': color,
        'year': year,
        'mileage': mileage,
        'price': price,
        'photo': file_path,
        'description': notes,
        'dealer_id': dealer_id,
        'sold': False
    }

    cars_collection.insert_one(car_data)

    return jsonify({'message': 'Машину успішно додано!'}), 200


@ app.route('/api/cars/filter', methods=['POST'])
def filter_cars():
    data = request.get_json()
    filters = {}
    sort_criteria = []

    if 'brands' in data and data['brands']:
        if 'all' not in data['brands']:
            filters['brand'] = {'$in': data['brands']}

    if 'price_min' in data and data['price_min'] is not None and 'price_max' in data and data['price_max'] is not None:
        filters['price'] = {'$gte': data['price_min'],
                            '$lte': data['price_max']}

    if 'mileage_max' in data and data['mileage_max'] is not None:
        filters['mileage'] = {'$lte': data['mileage_max']}

    if 'year_min' in data and data['year_min'] is not None and 'year_max' in data and data['year_max'] is not None:
        filters['year'] = {'$gte': data['year_min'],
                           '$lte': data['year_max']}

    if 'sort' in data:
        sort_option = data['sort']
        if sort_option == 'price-asc':
            sort_criteria.append(('price', 1))
        elif sort_option == 'price-desc':
            sort_criteria.append(('price', -1))
        elif sort_option == 'year-asc':
            sort_criteria.append(('year', 1))
        elif sort_option == 'year-desc':
            sort_criteria.append(('year', -1))
        elif sort_option == 'mileage-asc':
            sort_criteria.append(('mileage', 1))
        elif sort_option == 'mileage-desc':
            sort_criteria.append(('mileage', -1))

    cars = list(cars_collection.find(filters).sort(sort_criteria))

    user = get_current_user()
    if (user != None):
        if (isDealer()["dealer"]):
            dealer = dealers_collection.find_one({"user_id": user["_id"]})
            cars = list(filter(
                lambda car: car["dealer_id"] == dealer["_id"], cars))
        else:
            cars = list(filter(
                lambda car: car["sold"] == False, cars))
    for car in cars:
        car['_id'] = str(car['_id'])
        car['dealer_id'] = str(car['dealer_id'])

    return jsonify(cars), 200


@ app.route('/api/cars/data', methods=['GET'])
def get_car_data():
    brands = cars_collection.distinct('brand')

    years = cars_collection.distinct('year')

    return jsonify({'brands': brands, 'years': years}), 200


@ app.route('/api/cars/<id>', methods=['DELETE'])
@ role_required("owner", "admin")
def delete_car(id):
    cars_collection.delete_one({'_id': ObjectId(id)})
    return get_cars()


@ app.route('/api/collections', methods=['GET'])
def get_collections():
    collections_info = {}
    collection_names = db.list_collection_names()
    for collection_name in collection_names:
        collection = db[collection_name]
        document_count = collection.count_documents({})
        collections_info[collection_name] = document_count
    return jsonify(collections_info)


@ app.route('/api/collections/<name>', methods=['GET'])
def get_collection(name):
    if name not in db.list_collection_names():
        return jsonify({"error": "Колекцію не знайдено"}), 404

    collection = list(db[name].find({}))
    response = get_collection_info(collection, name)

    return jsonify(response), 200


@ app.route('/api/collections/<name>', methods=['DELETE'])
@ role_required("owner")
def delete_collection(name):
    db[name].drop()
    collection_names = db.list_collection_names()
    return jsonify(collection_names), 200


@ app.route('/api/collections/<name>', methods=['POST'])
@ role_required("owner")
def create_collection(name):
    try:

        if not name:
            return jsonify({'error': 'Необхідна назва колекції'}), 400

        collection = db[name]
        collection.insert_one({"status": "dummy_data"})
        return jsonify({'message': f'Колекція "{name}" успішно створена'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ app.route('/api/collections/document/delete/<collection_name>/<document_id>', methods=['DELETE'])
@ role_required("owner", "admin")
def delete_document(collection_name, document_id):
    db[collection_name].delete_one({"_id": ObjectId(document_id)})
    return jsonify({"message": "Документ успішно видалено"}), 200


@ app.route('/api/collections/document/update/<collection_name>/<document_id>', methods=['PUT'])
@ role_required("owner", "admin", "operator")
def update_document(collection_name, document_id):
    updated_data = request.json
    db[collection_name].update_one(
        {"_id": ObjectId(document_id)}, {"$set": updated_data})
    return jsonify({"message": "Документ успішно оновлено"}), 200


@ app.route('/api/collections/column/<collection_name>/<column_name>', methods=['DELETE'])
@ role_required("owner", "admin")
def delete_column(collection_name, column_name):
    db[collection_name].update_many({}, {"$unset": {column_name: ""}})
    return jsonify({"message": "Поле успішно видалене"}), 200


@ app.route('/api/collection/add-column/<collection_name>/<column_name>/<column_type>', methods=['POST'])
@ role_required("owner", "admin")
def add_column(collection_name, column_name, column_type):
    if not column_type:
        return jsonify({"error": "Необхідний тип поля"}), 400

    if not column_name:
        return jsonify({"error": "Необхідна назва поля"}), 400
    default_value = ""
    if column_type == "string":
        default_value = ""
    elif column_type == "int":
        default_value = 0
    elif column_type == "float":
        default_value = 0.0
    elif column_type == "boolean":
        default_value = False
    else:
        return jsonify({"error": "Невизначений тип поля"}), 400
    db[collection_name].update_many({}, {"$set": {column_name: default_value}})
    return jsonify({"message": "Поле успішно додане"}), 200


@ app.route('/api/collection/add-document/<collection_name>', methods=['POST'])
@ role_required("owner", "admin", "operator")
def add_document(collection_name):
    data = request.get_json()

    result = db[collection_name].insert_one(data)
    if result.inserted_id:
        return jsonify({"message": "Документ успішно додано", "id": str(result.inserted_id)}), 200
    else:
        return jsonify({"error": "Не вдалося додати документ"}), 500


@ app.route('/api/orders', methods=['POST'])
def create_order():
    user = get_current_user()

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json
    car_id = data.get('car_id')

    car = cars_collection.find_one({"_id": ObjectId(car_id)})
    if not car:
        return jsonify({"error": "Car not found"}), 404
    if isDealer()["dealer"]:
        return jsonify({"error": "Dealer can`t buy car"}), 404

    payment_type = random.choice(["credit", "cash", "other"])
    client = clients_collection.find_one({"user_id": user["_id"]})
    client_id = client["_id"]
    contract_data = {
        "contract_code": str(ObjectId()),
        "client_id": client_id,
        "dealer_id": car.get("dealer_id"),
        "contract_date": datetime.now().isoformat(),
        "car_id": car['_id'],
        "car_brand": car['brand'],
        "car_photo": car['photo'],
        "car_year": car['year'],
        "car_mileage": car['mileage'],
        "sale_date": datetime.now().isoformat(),
        "sale_price": car['price'],
        "payment_type": payment_type,
        "outdated": random.choice([True, False]),
    }

    contracts_collection.insert_one(contract_data)
    cars_collection.update_one({"_id": ObjectId(car_id)}, {
                               "$set": {"sold": True}})
    return jsonify({"success": True, "message": "Order placed successfully!"}), 201


@ app.route('/api/collections/clients/multiple-purchases', methods=['GET'])
def get_clients_with_multiple_purchases():
    pipeline = [
        {
            "$lookup": {
                "from": "contracts",
                "localField": "_id",
                "foreignField": "client_id",
                "as": "contracts_info"
            }
        },
        {
            "$addFields": {
                "contracts_count": {"$size": "$contracts_info"}
            }
        },
        {
            "$match": {
                "contracts_count": {"$gt": 1}
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "contracts_count": 1
            }
        }
    ]

    clients = list(clients_collection.aggregate(pipeline))
    response = get_collection_info(clients, "clients")

    return jsonify(response), 200


@ app.route('/api/dealers/top', methods=['GET'])
def get_top_dealers():
    pipeline = [
        {"$group": {"_id": {"dealer": "$dealer_id"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$lookup": {
            "from": "dealers",
            "localField": "_id.dealer",
            "foreignField": "_id",
            "as": "dealer_info"
        }},
        {
            "$limit": 1
        },
        {"$unwind": "$dealer_info"},
        {"$project": {
            "_id": "$dealer_info._id",
            "login": "$dealer_info.login",
            "role": "$dealer_info.role",
            "name": "$dealer_info.name",
            "city": "$dealer_info.city",
            "address": "$dealer_info.address",
            "phone": "$dealer_info.phone",
            "photo": "$dealer_info.photo"
        }}
    ]

    dealers = list(contracts_collection.aggregate(pipeline))
    response = get_collection_info(dealers, "dealers")
    return jsonify(response), 200


@ app.route('/api/contracts/credit', methods=['GET'])
def get_credit_contracts():
    contracts = list(contracts_collection.find({"payment_type": "credit"}))
    fields = set()
    for contract in contracts:
        fields.update(contract.keys())
        for key in contract.keys():
            if isinstance(contract[key], ObjectId):
                contract[key] = str(contract[key])
    response = {
        "fields": list(fields),
        "documents": contracts
    }
    return jsonify(response), 200


@ app.route('/api/clients/late-payments', methods=['GET'])
def get_clients_with_late_payments():
    pipeline = [
        {"$lookup": {
            "from": "contracts",
            "localField": "_id",
            "foreignField": "client_id",
            "as": "contracts_info"
        }},
        {"$unwind": "$contracts_info"},
        {"$match": {
            "contracts_info.outdated": True
        }},
        {"$group": {
            "_id": "$_id",
            "name": {"$first": "$name"},
            "late_payments": {"$sum": 1}
        }}
    ]

    clients = list(clients_collection.aggregate(pipeline))
    fields = set()

    for doc in clients:
        fields.update(doc.keys())
        for key in doc.keys():
            if isinstance(doc[key], ObjectId):
                doc[key] = str(doc[key])

    response = {
        "fields": list(fields),
        "documents": clients
    }
    return jsonify(response), 200


@ app.route('/api/cars/previous-owners', methods=['GET'])
def get_previous_owners():
    pipeline = [
        {"$lookup": {
            "from": "previous_owners",
            "localField": "_id",
            "foreignField": "car_id",
            "as": "previous_owners_info"
        }},
        {"$unwind": "$previous_owners_info"},
        {"$project": {
            "_id": 1,
            "previous_owners_info": 1
        }}
    ]

    cars = list(cars_collection.aggregate(pipeline))
    fields = set()

    for doc in cars:
        fields.update(doc.keys())
        for key in doc.keys():
            if isinstance(doc[key], ObjectId):
                doc[key] = str(doc[key])

    response = {
        "fields": list(fields),
        "documents": cars
    }
    return jsonify(response), 200


@ app.route('/api/contracts/by-date', methods=['GET'])
def get_contracts_by_date():
    pipeline = [
        {"$sort": {"date": 1}}
    ]

    contracts = list(contracts_collection.aggregate(pipeline))
    fields = set()

    for contract in contracts:
        fields.update(contract.keys())
        for key in contract.keys():
            if isinstance(contract[key], ObjectId):
                contract[key] = str(contract[key])

    response = {
        "fields": list(fields),
        "documents": contracts
    }
    return jsonify(response), 200


@ app.route('/api/clients-cars/payment', methods=['GET'])
def get_clients_and_cars_by_payment():
    pipeline = [
        {
            "$lookup": {
                "from": "contracts",
                "localField": "_id",
                "foreignField": "client_id",
                "as": "contracts_info"
            }
        },
        {
            "$unwind": "$contracts_info"
        },
        {
            "$lookup": {
                "from": "cars",
                "localField": "contracts_info.car_id",
                "foreignField": "_id",
                "as": "car_info"
            }
        },
        {
            "$unwind": "$car_info"
        },
        {
            "$project": {
                "_id": 1,
                "client": "$name",
                "car_id": "$car_info._id",
                "car_brand": "$car_info.brand",
                "car_model": "$car_info.model",
                "car_price": "$car_info.price",
                "car_color": "$car_info.color",
                "car_year": "$car_info.year",
                "payment_type": "$contracts_info.payment_type"
            }
        }
    ]

    clients_and_cars = list(clients_collection.aggregate(pipeline))
    fields = set()

    for doc in clients_and_cars:
        fields.update(doc.keys())
        for key in doc.keys():
            if isinstance(doc[key], ObjectId):
                doc[key] = str(doc[key])

    response = {
        "fields": list(fields),
        "documents": clients_and_cars
    }
    return jsonify(response), 200


@ app.route('/api/contracts/per-client', methods=['GET'])
def get_contracts_per_client():
    pipeline = [
        {"$group": {
            "_id": "$client_id",
            "contract_count": {"$sum": 1}
        }},
        {"$lookup": {
            "from": "clients",
            "localField": "_id",
            "foreignField": "_id",
            "as": "client_info"
        }},
        {"$unwind": "$client_info"},
        {"$project": {
            "_id": "$client_info._id",
            "name": "$client_info.name",
            "contract_count": 1
        }}
    ]

    contracts_per_client = list(contracts_collection.aggregate(pipeline))
    fields = set()

    for doc in contracts_per_client:
        fields.update(doc.keys())
        for key in doc.keys():
            if isinstance(doc[key], ObjectId):
                doc[key] = str(doc[key])

    response = {
        "fields": list(fields),
        "documents": contracts_per_client
    }
    return jsonify(response), 200


@ app.route('/api/contracts/per-dealer', methods=['GET'])
def get_contracts_per_dealer():
    pipeline = [
        {"$group": {
            "_id": "$dealer_id",
            "contract_count": {"$sum": 1}
        }},
        {"$lookup": {
            "from": "dealers",
            "localField": "_id",
            "foreignField": "_id",
            "as": "dealer_info"
        }},
        {"$unwind": "$dealer_info"},
        {"$project": {
            "_id": "$dealer_info._id",
            "login": "$dealer_info.login",
            "contract_count": 1
        }}
    ]

    contracts_per_dealer = list(contracts_collection.aggregate(pipeline))
    fields = set()

    for doc in contracts_per_dealer:
        fields.update(doc.keys())
        for key in doc.keys():
            if isinstance(doc[key], ObjectId):
                doc[key] = str(doc[key])

    response = {
        "fields": list(fields),
        "documents": contracts_per_dealer
    }
    return jsonify(response), 200


@ app.route('/api/sales/sum', methods=['GET'])
def get_sales_summary():
    pipeline = [
        {"$match": {"sold": True}},
        {"$group": {
            "_id": {"model": "$model", "brand": "$brand"},
            "total_sales": {"$sum": "$price"}
        }},
        {"$project": {
            "_id": 0,
            "model": "$_id.model",
            "brand": "$_id.brand",
            "total_sales": 1
        }},
        {"$sort": {"brand": 1, "model": 1}}
    ]

    result = list(cars_collection.aggregate(pipeline))

    response = {
        "fields": ["model", "brand", "total_sales"],
        "documents": result
    }

    return jsonify(response), 200


@ app.route('/api/pages', methods=['GET'])
def get_pages():
    pages = {'/': 'Головна', 'statistics': 'Статистика'}
    pages['collections'] = 'Колекції'
    user = get_current_user()
    if (user == None):
        return jsonify(pages), 200
    if isDealer()["dealer"]:
        pages['profile'] = 'Профіль'
    role = user['role']
    if (role == 'admin' or role == 'owner'):
        pages['users'] = 'Користувачі'

    return jsonify(pages), 200


if __name__ == '__main__':
    app.run(debug=True)
