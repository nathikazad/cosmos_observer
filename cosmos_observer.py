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
	threading.Timer(60, start_timer).start()
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
from flask_restful import Resource, Api, reqparse

app = Flask(__name__)
api = Api(app)

class Validators(Resource):
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
	def get(self, address):
		db = sqlite3.connect('mydb')
		cursor = db.cursor()

		parser = reqparse.RequestParser()
		parser.add_argument('start_time', type=str)
		parser.add_argument('end_time', type=str)
		parser.add_argument('number_of_points', type=int)
		args = parser.parse_args()

		# Validate the Parameters
		cursor.execute('''SELECT id FROM validators WHERE address = ? ''',(address, ))
		entry = cursor.fetchone()
		if entry is None:
			return Response(json.dumps({"Error": "Invalid Validator Address: "+address}), status=200, mimetype='application/json')
		validator_id = entry[0]
		cursor.execute('''SELECT MIN(snap_time), MAX(snap_time) FROM snapshots''')
		snaptime_bounds = cursor.fetchall()
		if not args['start_time']:
			args['start_time'] = snaptime_bounds[0][0]
		if not args['end_time']:
			args['end_time'] = snaptime_bounds[0][1]
		if not args['number_of_points']:
			args['number_of_points'] = 20
		cursor.execute('''SELECT COUNT(id) FROM snapshots''')
		total_snapshots = cursor.fetchone()[0]
		if args['number_of_points'] > total_snapshots:
			args['number_of_points'] = total_snapshots



		# Find the indices
		# print "Start time "+ args['start_time'] + " End Time " + args['end_time']
		cursor.execute('''SELECT MIN(id), MAX(id) FROM snapshots WHERE snap_time BETWEEN ? AND ?''', (args['start_time'], args['end_time']))
		snapshot_id_bounds = cursor.fetchall()
		#print snapshot_id_bounds[0]
		if snapshot_id_bounds[0][0] is None:
			return Response(json.dumps({"Error": "Invalid Time Parameters"}), status=200, mimetype='application/json')
		snapshot_id_min = snapshot_id_bounds[0][0]
		snapshot_id_max = snapshot_id_bounds[0][1]
		snapshot_id_interval = (snapshot_id_max - snapshot_id_min) / args['number_of_points']
		if snapshot_id_interval == 0:
			snapshot_id_interval = 1
		#print "Min ID: " + str(snapshot_id_min) + " Max ID: " + str(snapshot_id_max) + " INTERVAL: " + str(snapshot_id_interval) + " Number of points: " + str(args['number_of_points'])

		
		# Retrieve all the matching IDs
		cursor.execute('''SELECT id, snap_time FROM snapshots WHERE id >= ? AND id % ? = 0 AND id <= ?  ORDER BY id''', ( snapshot_id_min, snapshot_id_interval, snapshot_id_max))
		snapshots = cursor.fetchall()
		len(snapshots)
		
		# Retrieve the matching snapshots
		history = []
		for row in snapshots:
			cursor.execute('''SELECT voting_power FROM snapshot_entries WHERE validator_id = ? AND snapshot_id = ?''',(validator_id, row[0]))
			voting_power_snapshot = cursor.fetchone()
			if voting_power_snapshot:
				history.append({'voting_power':voting_power_snapshot[0], 'time_stamp':row[1], 'up':True})
			else:
				history.append({'voting_power':0, 'time_stamp':row[1], 'up':False})
		history = history[0:args['number_of_points']]

		# Calculate Average Up Time 
		cursor.execute('''SELECT COUNT(id) FROM snapshot_entries WHERE validator_id = ?''', (validator_id,))
		total_snapshots_for_validator = cursor.fetchone()[0]
		average_uptime = total_snapshots_for_validator * 100 / total_snapshots

		# Find most recent voting power
		cursor.execute('''SELECT voting_power FROM validators WHERE id = ? ''',(validator_id, ))
		voting_power  = cursor.fetchone()[0]

		db.close()

		return Response(json.dumps({"voting_power": voting_power, "uptime":average_uptime, "snapshots":history}), status=200, mimetype='application/json')


api.add_resource(Validators, '/validators')
api.add_resource(Validator, '/validator/<string:address>')
start_timer()
app.run(host= '0.0.0.0')


				
