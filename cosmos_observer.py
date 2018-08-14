import json
import requests
import sqlite3
import threading


def get_data(address, endpoint):
	try:
		json_data = requests.get("http://"+address+":26657/"+endpoint, timeout = 1).json()
		return json_data['result']
	except:
		return False

def update_validators(cursor):
	data = requests.get("http://138.197.200.70:26657/validators").json()

	cursor.execute('''UPDATE validators SET voting_power=0''')
	cursor.execute('''INSERT INTO snapshots(total_nodes, snap_time, block_height) 
		VALUES(?,datetime('now', 'localtime'),?)''', (len(data['result']['validators']), data['result']['block_height']))
	snapshot_id = cursor.lastrowid
	for validator in data['result']['validators']:
		cursor.execute('''INSERT OR IGNORE INTO validators(pub_key)
		        VALUES(?)''', (validator['pub_key']['value'],))
		cursor.execute('''UPDATE validators SET voting_power = ?, address = ? WHERE pub_key= ?''', 
				(int(validator['voting_power']), validator['address'],validator['pub_key']['value']))
		
		cursor.execute('''SELECT id FROM validators WHERE pub_key = ? ''', (validator['pub_key']['value'],))
		cursor.execute('''INSERT INTO snapshot_entries(validator_id, snapshot_id, voting_power) 
			VALUES(?,?,?)''', (cursor.fetchone()[0], snapshot_id,int(validator['voting_power'])))

def start_timer():
	threading.Timer(1, start_timer).start()
	db = sqlite3.connect('mydb')
	cursor = db.cursor()
	update_validators(cursor)
	db.commit()

# db = sqlite3.connect(':memory:')
db = sqlite3.connect('mydb')
cursor = db.cursor()
try:
	cursor.execute('''
	    CREATE TABLE validators(id INTEGER PRIMARY KEY, name TEXT,
	                       pub_key TEXT unique, voting_power INTEGER, address TEXT,
							 ip_address TEXT)
		''')
	cursor.execute('''CREATE TABLE snapshots(id INTEGER PRIMARY KEY, total_nodes INTEGER, 
								snap_time DATETIME, block_height TEXT)''')
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

	update_validators(cursor)
	db.commit()


	response = requests.get("http://138.197.200.70:26657/net_info")
	json_data = json.loads(response.text)

	peer_addresses = []
	for peer in json_data['result']['peers']:
		peer_address =  peer['node_info']['listen_addr'].split(':')[0]
		if peer_address not in peer_addresses:
			# print str(len(peer_addresses)) + ": " + peer_address + " " + peer['node_info']['moniker']
			data = get_data(peer_address, "status")
			if data != False:
				cursor.execute('''INSERT OR IGNORE INTO validators(name, voting_power, address, ip_address, pub_key) VALUES(?,?,?,?,?)''', 
					(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], peer_address, data['validator_info']['pub_key']['value']))
				cursor.execute('''UPDATE validators SET name = ?, voting_power = ?, address = ?, ip_address = ? WHERE pub_key= ?''', 
					(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], peer_address, data['validator_info']['pub_key']['value']))
			peer_addresses.append(peer_addresses)
			try:
				new_json_data = requests.get("http://"+peer_address+":26657/net_info", timeout = 1).json()
				for new_peer in new_json_data['result']['peers']:
					new_peer_address =  new_peer['node_info']['listen_addr'].split(':')[0]
					if new_peer_address not in peer_addresses:
						# print str(len(peer_addresses)) + ": " + new_peer_address + " " + new_peer['node_info']['moniker']
						data = get_data(new_peer_address, "status")
						if data != False:
							cursor.execute('''INSERT OR IGNORE INTO validators(name, voting_power, address, ip_address, pub_key) VALUES(?,?,?,?,?)''', 
								(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], new_peer_address, data['validator_info']['pub_key']['value']))
							cursor.execute('''UPDATE validators SET name = ?, voting_power = ?, address = ?, ip_address = ? WHERE pub_key= ?''', 
								(data['node_info']['moniker'], int(data['validator_info']['voting_power']), data['validator_info']['address'], new_peer_address, data['validator_info']['pub_key']['value']))
						peer_addresses.append(new_peer_address)
			except requests.exceptions.ConnectTimeout:
				pass
			except requests.exceptions.ConnectionError:
				pass

	db.commit()
except:
	print "error"

db.close()

from flask import Flask, request, jsonify, render_template, Response
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

class Cosmos(Resource):
    def get(self):
    	db = sqlite3.connect('mydb')
    	cursor = db.cursor()
    	cursor.execute('''SELECT name, pub_key, voting_power, address, ip_address FROM validators WHERE voting_power > 0''')
    	array = []
    	for row in cursor:
    		array.append({'name':row[0], 'pub_key':row[1], 'voting_power':row[2], 'address':row[3], 'ip':row[4]})
    	db.close()
        return Response(json.dumps(array), status=200, mimetype='application/json')

class Validator(Resource):
    def get(self, validator_id):
    	db = sqlite3.connect('mydb')
    	cursor = db.cursor()
    	cursor.execute('''SELECT MAX(id) FROM snapshots''')
    	max_snap_shot_id = cursor.fetchone()[0]
    	number_of_data_points = 20
    	cursor.execute('''Select id, snap_time FROM snapshots WHERE id % ? = 0 ORDER BY id''', (max_snap_shot_id/number_of_data_points,))
    	snapshots = cursor.fetchall()
    	query = 'select voting_power from snapshot_entries where validator_id =' + str(validator_id) + ' and snapshot_id in (' + ','.join((str(snapshot[0]) for snapshot in snapshots)) + ')'
    	cursor.execute(query)
    	voting_power_history = cursor.fetchall()
    	db.close()
    	history = [[voting_power_history[i][0], snapshots[i][1]] for i in range(20)]
    	return Response(json.dumps(history), status=200, mimetype='application/json')


api.add_resource(Cosmos, '/cosmos')
api.add_resource(Validator, '/validator/<int:validator_id>')
start_timer()
app.run(host= '0.0.0.0')


				
