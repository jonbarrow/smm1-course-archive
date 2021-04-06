'''
Credit Jonathan Barrow 2021

This will rip courses from SMM1 using NEX to automate the process
Use at your own risk, I am not resposible for any bans

Requires Python 3 and https://github.com/Kinnay/NintendoClients

Licensed under GNU GPLv3
'''

from nintendo.nex import backend, ranking, datastore_smm, settings, rmc, common, streams
from nintendo.games import SMM
from nintendo import nnas
from anynet import http
import anyio
import time
import sys
import os
import json

import logging
logging.basicConfig(level=logging.INFO)

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
	for course_id in range(sys.maxsize): # data_id is a uint64 so try all possible values
		time.sleep(1) # can be removed, used to not spam Nintendo servers too much
		#course_id = 0x03CF24CA # testing ID
		print('Trying course ID %d...' % course_id)
		try:
			# Get the course data URL
			param = datastore_smm.DataStorePrepareGetParam()
			param.data_id = course_id
			param.extra_data = []

			result = await datastore_smm_client.prepare_get_object(param)

			headers = {header.key: header.value for header in result.headers}
			course_data_url = result.url

			# Get course metadata

			metadata = {}

			param = DataStoreGetCustomRankingByDataIdParam()
			param.application_id = 0
			param.data_id_list = [course_id]
			param.result_option = 0x27

			result = await get_custom_ranking_by_data_id(param)

			ranking_result = result.ranking_result[0]
			meta_info = ranking_result.meta_info

			metadata['course_name'] = meta_info.name
			metadata['creator_pid'] = meta_info.owner_id
			metadata['stars'] = ranking_result.score
			metadata['user_plays'] = meta_info.ratings[0].info.total_value
			unknown1 = meta_info.ratings[1].info.total_value
			metadata['clears'] = meta_info.ratings[2].info.total_value
			metadata['total_attempts'] = meta_info.ratings[3].info.total_value
			metadata['failures'] = meta_info.ratings[4].info.total_value
			unknown2 = meta_info.ratings[5].info.total_value
			unknown3 = meta_info.ratings[6].info.total_value

			# Get course WR data

			param = DataStoreGetCourseRecordParam()
			param.data_id = course_id
			param.slot = 0

			result = await get_course_record(param)

			metadata['world_record'] = {}
			metadata['world_record']['best_time_pid'] = result.best_pid
			metadata['world_record']['first_complete_pid'] = result.first_pid
			metadata['world_record']['time_milliseconds'] = result.best_score
			metadata['world_record']['created_time'] = result.created_time.val
			metadata['world_record']['updated_time'] = result.updated_time.val

			# Download course and save metadata to disk

			response = await http.get(course_data_url, headers=headers)

			course_data_file = open('./courses/course-%d.bin' % course_id, 'wb')
			course_data_file.write(response.body)
			course_data_file.close()

			metadata_file = open('./courses/course-%d-metadata.json' % course_id, 'w', encoding='utf-8')
			json.dump(metadata, metadata_file, ensure_ascii=False, indent=4)
			metadata_file.close()

			print('Saved course ID %d' % course_id)
		except:
			print('Failed to get course %d' % course_id)
			pass


#########################################################
# Not implemented in NintendoClients, implementing here #
#########################################################

class DataStoreGetCustomRankingByDataIdParam(common.Structure):
	def __init__(self):
		super().__init__()
		self.application_id = None
		self.data_id_list = None
		self.result_option = None
	
	def load(self, stream):
		self.application_id = stream.u32()
		self.data_id_list = stream.list(stream.u64)
		self.result_option = stream.u8()
	
	def save(self, stream):
		stream.u32(self.application_id)
		stream.list(self.data_id_list, stream.u64)
		stream.u8(self.result_option)

class DataStoreCustomRankingResult(common.Structure):
	def __init__(self):
		super().__init__()
		self.order = None
		self.score = None
		self.meta_info = None
	
	def load(self, stream):
		self.order = stream.u32()
		self.score = stream.u32()
		self.meta_info = stream.extract(datastore_smm.DataStoreMetaInfo)
	
	def save(self, stream):
		stream.u32(self.order)
		stream.u32(self.score)
		stream.add(self.meta_info)

class DataStoreGetCourseRecordParam(common.Structure):
	def __init__(self):
		super().__init__()
		self.data_id = None
		self.slot = None
	
	def load(self, stream):
		self.data_id = stream.u64()
		self.slot = stream.u8()
	
	def save(self, stream):
		stream.u64(self.data_id)
		stream.u8(self.slot)

class DataStoreGetCourseRecordResult(common.Structure):
	def __init__(self):
		super().__init__()
		self.data_id = None
		self.slot = None
		self.first_pid = None
		self.best_pid = None
		self.best_score = None
		self.created_time = None
		self.updated_time = None
	
	def load(self, stream):
		self.data_id = stream.u64()
		self.slot = stream.u8()
		self.first_pid = stream.u32()
		self.best_pid = stream.u32()
		self.best_score = stream.s32()
		self.created_time = stream.datetime()
		self.updated_time = stream.datetime()
	
	def save(self, stream):
		stream.u64(self.data_id)
		stream.u8(self.slot)
		stream.u32(self.first_pid)
		stream.u32(self.best_pid)
		stream.s32(self.best_score)
		stream.datetime(self.created_time)
		stream.datetime(self.updated_time)

async def get_custom_ranking_by_data_id(param):
	#--- request ---
	stream = streams.StreamOut(datastore_smm_client.settings)
	stream.add(param)
	data = await datastore_smm_client.client.request(datastore_smm_client.PROTOCOL_ID, 50, stream.get())

	#--- response ---
	stream = streams.StreamIn(data, datastore_smm_client.settings)

	obj = rmc.RMCResponse()
	obj.ranking_result = stream.list(DataStoreCustomRankingResult)
	obj.results = stream.list(common.Result)

	return obj

async def get_course_record(param):
	#--- request ---
	stream = streams.StreamOut(datastore_smm_client.settings)
	stream.add(param)
	data = await datastore_smm_client.client.request(datastore_smm_client.PROTOCOL_ID, 72, stream.get())

	#--- response ---
	stream = streams.StreamIn(data, datastore_smm_client.settings)

	result = stream.extract(DataStoreGetCourseRecordResult)

	return result

anyio.run(main)