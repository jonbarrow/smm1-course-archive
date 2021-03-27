'''
Jonathan Barrow 2021

This will rip courses from SMM1 using NEX to automate the process
Use at your own risk, I am not resposible for any bans

Only downloads course data. Does not include metadata such as stars or time rankings

Requires Python 3 and https://github.com/Kinnay/NintendoClients
'''

from nintendo.nex import backend, ranking, datastore_smm, settings
from nintendo.games import SMM
from nintendo import nnas
from anynet import http
import anyio
import time
import sys
import os

import logging
logging.basicConfig(level=logging.FATAL)

# Unique device info
DEVICE_ID = 0
SERIAL_NUMBER = "REDACTED"
SYSTEM_VERSION = 0x260
REGION_ID = 4
COUNTRY_NAME = "US"
LANGUAGE = "en"

USERNAME = "REDACTED" #Nintendo network id
PASSWORD = "REDACTED" #Nintendo network password

# Globals
nas = None
nex_token = None
datastore_smm_client = None # set later

async def main():
	os.makedirs('./courses', exist_ok=True)

	await nas_login() # login with NNID
	await backend_setup() # setup the backend NEX client and start scraping

async def nas_login():
	global nas
	global nex_token

	nas = nnas.NNASClient()
	nas.set_device(DEVICE_ID, SERIAL_NUMBER, SYSTEM_VERSION)
	nas.set_title(SMM.TITLE_ID_EUR, SMM.LATEST_VERSION)
	nas.set_locale(REGION_ID, COUNTRY_NAME, LANGUAGE)
		
	access_token = await nas.login(USERNAME, PASSWORD)
	nex_token = await nas.get_nex_token(access_token.token, SMM.GAME_SERVER_ID)

async def backend_setup():
	global datastore_smm_client
	
	s = settings.default()
	s.configure(SMM.ACCESS_KEY, SMM.NEX_VERSION)

	async with backend.connect(s, nex_token.host, nex_token.port) as be:
		async with be.login(str(nex_token.pid), nex_token.password) as client:
			datastore_smm_client = datastore_smm.DataStoreClientSMM(client)

			await scrape() # start ripping courses

async def scrape():
	for lvl_id in range(sys.maxsize): # data_id is a uint64 so try all possible values
		time.sleep(1) # can be removed, used to not spam Nintendo servers too much
		print('Trying course ID %d...' % lvl_id)
		try:
			datastore_prepare_get_param = datastore_smm.DataStorePrepareGetParam()
			datastore_prepare_get_param.data_id = lvl_id
			datastore_prepare_get_param.extra_data = []

			datastore_req_get_info = await datastore_smm_client.prepare_get_object(datastore_prepare_get_param)

			headers = {header.key: header.value for header in datastore_req_get_info.headers}

			response = await http.get(datastore_req_get_info.url, headers=headers)

			f = open('./courses/course-%d.bin' % lvl_id, 'wb')
			f.write(response.body)
			f.close()

			print('Saved ./courses/course-%d.bin' % lvl_id)
		except:
			print('Failed to get course %d' % lvl_id)
			pass

anyio.run(main)