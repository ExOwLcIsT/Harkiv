from flask import Flask, request, jsonify, redirect, url_for, render_template
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from functools import wraps
import datetime
import os
app = Flask(__name__)

client = MongoClient('mongodb://localhost:27017/')
db = client['AutoSale']
users_collection = db['Keys']
clients_collection = db['clients']
dealers_collection = db['dealers']
contracts_collection = db['contracts']
cars_collection = db['cars']

UPLOAD_FOLDER = 'static/images/cars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if user and user['role'] in roles:
                return f(*args, **kwargs)
            else:
                return jsonify({"error": "Unauthorized access"}), 403
        return decorated_function
    return decorator

def get_current_user():
    user_login = request.cookies.get('username')
    if not user_login:
        return None
    user = users_collection.find_one({"login": user_login})
    return user



@app.route('/', methods=['GET'])
def get_index_page():
    return render_template(  
        "index.html"
    )

@app.route('/collections', methods=['GET'])
def get_collections_page():
    return render_template(  
        "collections.html"
    )

@role_required("owner", "admin")
@app.route('/users', methods=['GET'])
def get_users_page():
    return render_template(  
        "users.html"
    )

@app.route('/profile', methods=['GET'])
def get_profile_page():
    return render_template(  
        "profile.html"
    )

@app.route('/statistics', methods=['GET'])
def get_statistics_page():
    return render_template(  
        "statistics.html"   
    )

@role_required("owner", "admin")
@app.route('/api/users', methods=['GET'])
def get_users():
    users = list(users_collection.find({}))
    for user in users:
        user['_id'] = str(user['_id']) 
    return jsonify(users)


@role_required("owner", "admin")
@app.route('/api/users/<id>', methods=['DELETE'])
def delete_user(id):
    users_collection.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('get_users'))
@role_required("admin", "owner")
@app.route('/api/users/<user_id>/role', methods=['PUT'])
def update_user_role(user_id):
    if 'username' not in request.cookies:
        return jsonify({"message": "Unauthorized access"}), 401

    current_user = users_collection.find_one({"login": request.cookies['username']})
    if not current_user:
        return jsonify({"message": "Forbidden"}), 403

    data = request.json
    new_role = data.get('role')

    valid_roles = ['user', 'operator', 'admin', 'owner']
    if new_role not in valid_roles:
        return jsonify({"message": "Invalid role"}), 400

    users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": new_role}})
    
    return jsonify({"message": "Role updated successfully"}), 200


@app.route('/authorize/login', methods=['POST', 'GET'])
def login():
    login = request.form['login']
    password = request.form['password']
    user = users_collection.find_one({"login": login, "password": password}) 
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    response = jsonify({"login": user['login'], "role": user['role']})
    response.set_cookie('user', user['login'])
    return response, 200

@app.route('/authorize/signup', methods=['POST'])
def signup():
    login = request.form.get("login")
    password = request.form.get("password")
    name = request.form.get("name")
    city = request.form.get("city")
    address = request.form.get("address")
    phone = request.form.get("phone")
    photo = request.files.get("photo")

    existing_user = users_collection.find_one({"login": login})
    if existing_user:
        return jsonify({"success": False, "message": "User with this username already exists."}), 409
    
    if photo and allowed_file(photo.filename):
        filename = secure_filename(photo.filename)
        photo_path = os.path.join('static/images/dealers', filename)
        photo.save(photo_path)
    else:
        return jsonify({"success": False, "message": "Invalid photo format."}), 400

    role = "user"
    if users_collection.count_documents({}) == 0:
        role = "owner"
    
    users_collection.insert_one({
        "login": login, 
        "password": password, 
        "role": role, 
        "name": name, 
        "city": city, 
        "address": address, 
        "phone": phone,
        "photo": filename
    })

    return jsonify({"success": True, "login": login, "role": role})


@app.route('/api/cars', methods=['GET'])
def get_cars():
    print(get_current_user())
    cars = list(cars_collection.find({"sold": False, "dealer": {"$ne": get_current_user()["login"]}}))
    for car in cars:
        car['_id'] = str(car['_id'])
    return jsonify(cars)


@app.route('/api/cars', methods=['POST'])
def add_car():
    brand = request.form['brand']
    model = request.form['model']
    year = int(request.form['year'])
    mileage = int(request.form['mileage'])
    price = float(request.form['price'])
    notes = request.form['notes'],    
    color = request.form['color'],
    dealer = request.form['dealer']

    if 'photo' not in request.files:
        return jsonify({'error': 'No photo uploaded'}), 400
    
    photo = request.files['photo']
    if photo.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    filename = secure_filename(photo.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    photo.save(file_path)

    car_data = {
        'brand': brand,
        'model': model,
        'color': color,
        'year': year,
        'mileage': mileage,
        'price': price,
        'image': file_path,  
        'description': notes,
        'dealer': dealer,
        'sold': False
    }

    cars_collection.insert_one(car_data)

    return jsonify({'message': 'Car added successfully!'}), 200

@app.route('/api/cars/filter', methods=['POST'])
def filter_cars():
    data = request.get_json()
    filters = {}
    sort_criteria = []

    if 'brands' in data and data['brands']:
        if 'all' not in data['brands']:
            filters['brand'] = {'$in': data['brands']}  # Filter by selected brands

    if 'price_min' in data and data['price_min'] is not None and 'price_max' in data and data['price_max'] is not None:
        filters['price'] = {'$gte': data['price_min'], '$lte': data['price_max']}  # Filter by price range

    if 'mileage_max' in data and data['mileage_max'] is not None:
        filters['mileage'] = {'$lte': data['mileage_max']}  # Filter by maximum mileage

    if 'year_min' in data and data['year_min'] is not None and 'year_max' in data and data['year_max'] is not None:
        filters['year'] = {'$gte': data['year_min'], '$lte': data['year_max']}  # Filter by year range

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

    for car in cars:
        car['_id'] = str(car['_id'])

    return jsonify(cars), 200

@app.route('/api/cars/data', methods=['GET'])
def get_car_data():
    brands = cars_collection.distinct('brand')

    years = cars_collection.distinct('year')

    return jsonify({'brands': brands, 'years': years}), 200


@role_required("owner", "admin")
@app.route('/api/cars/<id>', methods=['DELETE'])
def delete_car(id): 
    cars_collection.delete_one({'_id': ObjectId(id)})
    return get_cars();


@role_required("owner","admin","operator")
@app.route('/api/collections', methods=['GET'])
def get_collections():
    collections_info = {}
    collection_names = db.list_collection_names()
    for collection_name in collection_names:
        collection = db[collection_name]
        document_count = collection.count_documents({})
        collections_info[collection_name] = document_count
    return jsonify(collections_info)



@role_required("owner","admin","operator")
@app.route('/api/collections/<name>', methods=['GET'])
def get_collection(name):
    if name not in db.list_collection_names():
        return jsonify({"error": "Collection not found"}), 404
    
    collection = db[name]
    documents = list(collection.find()) 

    fields = set()
    for doc in documents:     
        fields.update(doc.keys())
        doc['_id']= str(doc['_id'])
    if name == "Keys":
    
        fields.remove('password');
        for doc in documents:     
            doc['password'] = ""
       
    response = {
        "collection_name": name,
        "fields": list(fields),
        "documents": documents
    }

    return jsonify(response), 200



@role_required("owner","admin")
@app.route('/api/collections/<name>', methods=['DELETE'])
def delete_collections(name):
    db[name].drop()   
    collection_names = db.list_collection_names()
    return jsonify(collection_names), 200


@app.route('/api/orders', methods=['POST'])
def create_order():
    if 'username' not in request.cookies:
        return jsonify({"error": "Unauthorized"}), 401

    user_login = request.cookies.get('username')
    user = users_collection.find_one({"login": user_login})

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json
    car_id = data.get('car_id')
    comment = data.get('comment')

    car = cars_collection.find_one({"_id": ObjectId(car_id)})
    if not car:
        return jsonify({"error": "Car not found"}), 404

    dealer = users_collection.find_one({"login": car.get('dealer')})

    contract_data = {
        "contract_code": str(ObjectId()),
        "client_id": user['_id'],
        "dealer_id": dealer.get("_id"),
        "contract_date": datetime.datetime.now().isoformat(),
        "car_brand": car['brand'],
        "car_image": car['image'],
        "car_year": car['year'],
        "car_mileage": car['mileage'],
        "sale_date": None,
        "sale_price": car['price'],
        "note": comment
    }

    contracts_collection.insert_one(contract_data)
    cars_collection.update_one({"_id": ObjectId(car_id)}, {"$set": {"sold": True}})
    dealers_collection.insert_one(dealer)
    clients_collection.insert_one(get_current_user())
    return jsonify({"success": True, "message": "Order placed successfully!"}), 201


@app.route('/api/clients/all', methods=['GET'])
def get_all_clients():
    clients = list(clients_collection.find())
    for client in clients:
        client['_id'] = str(client['_id'])  # Convert ObjectId to string
    return jsonify(clients), 200

@app.route('/api/clients/multiple-purchases', methods=['GET'])
def get_clients_with_multiple_purchases():
    pipeline = [
        {"$lookup": {
            "from": "contracts",
            "localField": "_id",
            "foreignField": "client_id",
            "as": "contracts"
        }},
        {"$match": {"contracts.1": {"$exists": True}}}  # Match clients with more than 1 contract
    ]
    clients = list(clients_collection.aggregate(pipeline))
    for client in clients:
        client['_id'] = str(client['_id'])
    return jsonify(clients), 200

@app.route('/api/dealers/top', methods=['GET'])
def get_top_dealer():
    pipeline = [
        {"$group": {"_id": {"dealer": "$dealer_id", "month": {"$month": "$contract_date"}}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 1},
        {"$lookup": {
            "from": "dealers",
            "localField": "_id.dealer",
            "foreignField": "_id",
            "as": "dealer_info"
        }},
        {"$unwind": "$dealer_info"}
    ]
    top_dealer = list(contracts_collection.aggregate(pipeline))
    return jsonify(top_dealer), 200

@app.route('/api/contracts/credit', methods=['GET'])
def get_credit_contracts():
    contracts = list(contracts_collection.find({"payment_type": "credit"}))
    for contract in contracts:
        contract['_id'] = str(contract['_id'])
    return jsonify(contracts), 200


if __name__ == '__main__':
    app.run(debug=True)