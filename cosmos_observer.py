import json
import requests
import sqlite3


def get_data(address, endpoint):
	try:
		json_data = requests.get("http://"+address+":26657/"+endpoint, timeout = 1).json()
		return json_data['result']
	except:
		return False

# db = sqlite3.connect(':memory:')
db = sqlite3.connect('mydb')
cursor = db.cursor()
try:
	cursor.execute('''
	    CREATE TABLE validators(id INTEGER PRIMARY KEY, name TEXT,
	                       pub_key TEXT unique, voting_power INTEGER, address TEXT,
							 ip_address TEXT)
		''')
	cursor.execute('''CREATE TABLE snapshots(id INTEGER PRIMARY KEY, total_nodes INTEGER, snap_time DATETIME)''')
	cursor.execute('''CREATE TABLE snapshot_entries(id INTEGER PRIMARY KEY, validator_id INTEGER, 
							snapshot_id INTEGER, voting_power INTEGER)''')

	data = requests.get("http://138.197.200.70:26657/genesis").json()
	for validator in data['result']['genesis']['validators']:
		cursor.execute('''INSERT OR IGNORE INTO validators(name, pub_key)
	                  VALUES(?,?)''', (validator['name'],validator['pub_key']['value']))
	db.commit()

	for validator in data['result']['genesis']['app_state']['stake']['validators']:
		cursor.execute('''INSERT OR IGNORE INTO validators(name, pub_key)
	        VALUES(?,?)''', (validator['description']['moniker'],validator['pub_key']['value']))
		cursor.execute('''UPDATE validators SET name = ? WHERE pub_key= ?''', 
			(validator['description']['moniker'],validator['pub_key']['value']))
	db.commit()

	data = requests.get("http://138.197.200.70:26657/validators").json()

	for validator in data['result']['validators']:
		cursor.execute('''SELECT pub_key FROM validators WHERE pub_key = ? ''',
			(validator['pub_key']['value'],))
		entries = cursor.fetchall()
		if len(entries) >= 1:
			cursor.execute('''UPDATE validators SET voting_power = ?, address = ? WHERE pub_key= ?''', 
				(int(validator['voting_power']), validator['address'],validator['pub_key']['value']))
		else:
			cursor.execute('''INSERT OR IGNORE INTO validators(voting_power, address, pub_key)
		        VALUES(?,?,?)''', (int(validator['voting_power']), validator['address'], validator['pub_key']['value']))
	db.commit()


	# response = requests.get("http://138.197.200.70:26657/net_info")
	# json_data = json.loads(response.text)

	# peer_addresses = []
	# for peer in json_data['result']['peers']:
	# 	peer_address =  peer['node_info']['listen_addr'].split(':')[0]
	# 	if peer_address not in peer_addresses:
	# 		# print str(len(peer_addresses)) + ": " + peer_address + " " + peer['node_info']['moniker']
	# 		data = get_data(peer_address, "status")
	# 		if data != False:
	# 			cursor.execute('''INSERT OR IGNORE INTO validators(name, voting_power, address, ip_address, pub_key) VALUES(?,?,?,?,?)''', 
	# 				(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], peer_address, data['validator_info']['pub_key']['value']))
	# 			cursor.execute('''UPDATE validators SET name = ?, voting_power = ?, address = ?, ip_address = ? WHERE pub_key= ?''', 
	# 				(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], peer_address, data['validator_info']['pub_key']['value']))
	# 		peer_addresses.append(peer_addresses)
	# 		try:
	# 			new_json_data = requests.get("http://"+peer_address+":26657/net_info", timeout = 1).json()
	# 			for new_peer in new_json_data['result']['peers']:
	# 				new_peer_address =  new_peer['node_info']['listen_addr'].split(':')[0]
	# 				if new_peer_address not in peer_addresses:
	# 					# print str(len(peer_addresses)) + ": " + new_peer_address + " " + new_peer['node_info']['moniker']
	# 					data = get_data(new_peer_address, "status")
	# 					if data != False:
	# 						cursor.execute('''INSERT OR IGNORE INTO validators(name, voting_power, address, ip_address, pub_key) VALUES(?,?,?,?,?)''', 
	# 							(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], new_peer_address, data['validator_info']['pub_key']['value']))
	# 						cursor.execute('''UPDATE validators SET name = ?, voting_power = ?, address = ?, ip_address = ? WHERE pub_key= ?''', 
	# 							(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], new_peer_address, data['validator_info']['pub_key']['value']))
	# 					peer_addresses.append(new_peer_address)
	# 		except requests.exceptions.ConnectTimeout:
	# 			pass
	# 		except requests.exceptions.ConnectionError:
	# 			pass

	# db.commit()
except:
	pass


	


from flask import Flask, request, jsonify, render_template, Response
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

class Engine(Resource):
    def get(self):
    	db = sqlite3.connect('mydb')
    	cursor = db.cursor()
    	cursor.execute('''UPDATE validators SET voting_power=0''')
    	db.commit()
    	data = requests.get("http://138.197.200.70:26657/validators").json()
    	for validator in data['result']['validators']:
			cursor.execute('''SELECT pub_key FROM validators WHERE pub_key = ? ''', (validator['pub_key']['value'],))
			entries = cursor.fetchall()
			if len(entries) >= 1:
				cursor.execute('''UPDATE validators SET voting_power = ?, address = ? WHERE pub_key= ?''', 
					(int(validator['voting_power']), validator['address'],validator['pub_key']['value']))
			else:
				cursor.execute('''INSERT OR IGNORE INTO validators(voting_power, address, pub_key)
			        VALUES(?,?,?)''', (int(validator['voting_power']), validator['address'], validator['pub_key']['value']))
    	
    	db.commit()
    	cursor.execute('''SELECT name, pub_key, voting_power, address, ip_address FROM validators WHERE voting_power > 0''')
    	array = []
    	for row in cursor:
    		array.append({'name':row[0], 'pub_key':row[1], 'voting_power':row[2], 'address':row[3], 'ip':row[4]})
        return Response(json.dumps(array), status=200, mimetype='application/json')

api.add_resource(Engine, '/engine')
app.run(host= '0.0.0.0')
db.close()

				
