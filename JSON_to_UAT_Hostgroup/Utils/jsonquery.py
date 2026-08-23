import re
import logging
import pprint
import json

from flask_sqlalchemy  import SQLAlchemy

pp = pprint.PrettyPrinter(depth=6)
"""

Operando ->  operacion | funcion 


"""
inputval = re.compile(r'(/\w+)*(/*\[\s*(\d+)(:{1}\d+)*\s*\])*(\[\s*[@\w\!=<>\'"]+\s*\])*')


field = re.compile(r'[@\w!=<>\':\*"]')

_log = re.compile(r'^(and)|^(or)')

comp = re.compile(r'[!=<>]')

class States(object):

	def __init__(self, states):
		self._logger = logging.getLogger("States")
		self._states = states
		self._index = 0

	def __iter__(self):
		return self

	def __next__(self):

		current = self._states[self._index]
		self._logger.debug('indice: ' + str(self._index))
		self._logger.debug('retornando: ' + current)
		self._index += 1
		if self._index >= len(self._states):
			self._index = 0

		return current


def ffspace(text,idx):

	while idx < len(text):
		if text[idx] != ' ':
			return idx
		idx += 1
	return idx


def check(text):
	logger = logging.getLogger("check")
	text = text.lstrip().rstrip()
	operaciones = []
	operacion = {}
	operando = ''
	#-------------------
	idx = 0
	logger.debug('.' + text + '.')
	state1 = States(['operando','comparador','operando','logical','close'])
	state = next(state1)
	logger.debug(state)

	while True:
		
		if state == 'close' or len(text) == idx:
			logger.debug('close')
			operacion.update({ 'operando2': operando })
			operaciones.append(  operacion.copy())
			operacion.clear()
			operando =''
			state = next(state1)
			idx = ffspace(text,idx)
			if idx >= len(text):
				break
			continue

		if text[idx] == ' ':
			logger.debug('Space ' + str(idx))
			if state == 'operando' or state == 'logical':
				state = next(state1)
			idx += 1
			continue

		# and  /  or
		if state == 'logical':
			logger.debug(text[idx:idx+3])
			if _log.match(text[idx:idx+3]):
				operacion.update({ 'logical' : text[idx:idx+3]})				
				idx += 3
				state = next(state1)
				continue
			else:
				raise Exception('Se esperaba un operador logic and / or en: ' + str(idx))

		if text[idx] in ['!','>','<','='] and state == 'operando':
			state = next(state1)
			logger.debug(state)

		if state == 'comparador':
			logger.debug('comparador')
			logger.debug(text[idx:idx+2])
			operacion.update({ 'operando1': operando })
			operando = ''
			#validar el operador
			operacion.update({ 'operador' : text[idx:idx+2]})
			idx = ffspace(text,idx + 2)
			logger.debug(text[idx])
			state = next(state1)
			
		
		if state == 'operando' and field.match(text[idx]):
			#logger.debug('---> ' + str(text[idx]))
			operando += text[idx]
		# else:
		# 	raise Exception('Se esperaba un comparador: ' + text[idx])

		idx += 1
		if idx > len(text):
			break

	return operaciones


def groups(text):
	logger = logging.getLogger("groups")
	idGroup = 0
	idx = 0
	groupname = 'group' + str(idGroup) +'-0'
	groups = { groupname: []}
	temp = ''
	level = 0
	function = False
	function_level = 0
	while idx < len(text):

		if text[idx:idx+3] == 'fn:':
			logger.debug('function')
			logger.debug('Level ' +str(function_level))
			function_level += 1
			function = True

		if text[idx] == '(' and not function:  #open group
			logger.debug('open group ' + groupname)
			groups[groupname].append(temp)
			temp = ''

			idGroup += 1 if idx > 0 and not _open else 0

			groupname = 'group' + str(idGroup) + '-' + str(level)

			groups.update({groupname : [] })  #init
			level += 1
			idx += 1
			_open = True
			continue


		if  text[idx] == ')' and function:
			logger.debug('Close function Level: ' +str(function_level))
			function_level -= 1
			
			function = False if function_level == 0 else True
			temp+=text[idx] 
			idx+= 1
			continue

		if text[idx] == ')':
			#cierra grupoe
			logger.debug('close group')
			_open = False
			groups[groupname].append(temp)
			temp = ''
			level -= 1
			groupname = 'group' + str(idGroup) + '-' + str(level)
			idx += 1
			continue

		temp += text[idx] #if text[idx] != ' ' else ''

		idx += 1

	#logger.debug(len(groups['group0-0']))
	if len(groups) == 1 and len(groups['group0-0']) == 0: # En caso que no hay parentesis
		groups['group0-0'] = temp

	return groups

def createProgram(query):
	grps = groups(query)
	logger = logging.getLogger("test")
	group_plan = {}
	

	for key,value in grps.items():
		key = key.replace('group','')
		idgrp = key.split('-')[0]
		level = key.split('-')[1]
		groupname = 'group' + str(idgrp)
		print(key)
		print(idgrp)
		
		plan = check(''.join(value))

		if groupname in group_plan:
			logger.debug(level)
			group = group_plan[groupname]
			logger.debug('level: ' + str(level))
			group.append({ 'suboperacion' : plan} )
		else:
			group_plan.update ({ groupname : plan })

	return group_plan


def extractIndexs(text):

	name= text[0:text.find('[')] if text.find('[')>=0 else text

	q1 = text[ text.find('[') +1 : text.find(']') ] if text.find('[') >= 0 else ''
	idxpattern = re.compile(r'\d+:{0,1}\d*')
	newidx = None
	if idxpattern.match(q1):
		i = q1.split(':') 
		newidx = slice(int(i[0]),int(i[1])) if len(i) > 1 else int(i[0])
		offset = text.find(']') + 1
	else:
		offset = 0

	
	q2 = text[text.find('[',offset) + 1: text.find(']',offset)] \
	     if text.find('[',offset) >= 0 else ''
	select = text[ text.find('{')+1:text.find('}')].split(',') if text.find('{') >= 0 else None
	if select is not None:
		select = list(map(lambda item: item.replace('"','').replace('\'',''),select))
	return name,newidx,q2,select



def nodeParse(text):

	logger = logging.getLogger("nodeParse")
	#logger.debug(text)
	#nname = re.compile(r'\w')
	#nidx = re.compile(r'\d')
	f1 = re.compile(r'([\w])*(\[\d+[:{1}\d]*\])*(\[[@\w=>\!<"\']+\])*')
	if f1.match(text):
		name, q1,q2,select = extractIndexs(text)
		logger.debug('check')
		logger.debug({ 'path' : name , 'idx' : q1, 'query': q2 , 'select': select })
		return { 'path' : name , 'idx' : q1, 'query': q2 , 'select': select }
	else:
		raise Exception('Syntax error over: ' + text)
	

def filterFields(dataset,select):
	
	if select is None or select == '' or select == '*' :
		return dataset
	res = {}
	[ res.update({ k : v }) for k,v in dataset.items() if k in select]
	return res

def executeQuery(query,dataset,select):
	logger = logging.getLogger("executeQuery")
	logger.debug('ejecutando query')
	logger.debug(select)
	
	def execOperaciones(oprs,data):

		result = []  
		op_log = None
		subset = data.copy()
		for oper in oprs:  # cada operacion es un conjunto de dataset
			logger.debug('Operacion: ' + str(oper))

			if op_log == 'and':
				logger.debug('AND')
				logger.debug(len(result))
				subset = result.copy() #if len(result)>0 else subset
				result = []
			elif op_log == 'or':
				logger.debug('OR')
				subset = data.copy()

			op1 = oper['operando1']
			op2 = oper['operando2']
			comp = oper['operador']
			op_log = oper['logical'] if 'logical' in oper else None
			
			#select
			for dataitem in subset:  
				logger.debug('loop') 
				fieldname = op1[1:] if op1[0] == '@' else op2[1:]
				
				fieldvalue = dataitem[fieldname]
				logger.debug(fieldvalue)
				
				if isinstance(fieldvalue,list):
					logger.debug('--------->>>>>')
					value = op2.replace('"','').replace('\'','')
					logger.debug(value)
					logger.debug(value in fieldvalue)
					logger.debug(comp)
					if comp == '==' and value in fieldvalue:
						logger.debug('IN')
						result.append(filterFields(dataitem,select))
					elif comp == '!=' and value not in fieldvalue:
						logger.debug('NOT IN')
						result.append(filterFields(dataitem,select))
				elif isinstance(fieldvalue,str):
					value = op2
					o = 'fieldvalue' + comp + value
					logger.debug(o)
					if eval(o,{'fieldvalue' : fieldvalue}):
						logger.debug('True')
						result.append(filterFields(dataitem,select))
			
		return result

	#Por cada grupo
	for label , item in query.items():
		logger.debug(label)
		logger.debug(item)
		logger.debug('---------------')
		r = execOperaciones(item,dataset)
		return r


def findnode(dataset,nodename):
	logger = logging.getLogger("findnode")
	result = []

	if isinstance(dataset,dict):
		logger.debug('---------')
		for key,value in dataset.items():
			if key == nodename:
				logger.debug('Check: ' + key)
				result += [ value ]
				logger.debug(result)
				return result
			else:
				logger.debug('sub')
				result += findnode(value,nodename)
		logger.debug(result)
		logger.debug('---------')

	elif isinstance(dataset,list):
		logger.debug('list')
		for item in dataset:
			result += findnode(item,nodename)
	else:
		#logger.warning(type(dataset))
		return result
		#raise Exception('El dataset debe ser list o un dict')
	return result

def processPath(text,query):

	def  empty(value):
		if isinstance(value,str):
			value = value.rstrip().lstrip()
			return value == '' or len(value) == 0 or value is None
		else:
			return value is None

	logger = logging.getLogger("seekPath")

	if len(text) == 0:
		return None

	root = True if query[0] == '/' else False

	nodes = query.split('/')

	if not root:
		logger.debug('Realizando busqueda')
		result = findnode(text,nodes[0]) 
		#si son nodos finales
		isfinal = True
		for item in result:
			isfinal = isfinal and (False if isinstance(item,dict) or isinstance(item,list) else True)
		if isfinal:
			return result
	else:
		result = text.copy()

	logger.debug(len(result))

	#cortar
	node = []
	for selectNode in filter(None ,nodes): #text

		logger.debug('Nodo seleccionado: ' + selectNode)
		nodeQuery = nodeParse(selectNode) #parsea la query
		#----------- 
		logger.debug(nodeQuery)
		logger.debug('----->')

		path,selIndex,query,select = \
		nodeQuery['path'],nodeQuery['idx'],nodeQuery['query'],nodeQuery['select']
		logger.debug('buscando nodo: ' + path)
		logger.debug(isinstance(result,list))
		logger.debug(type(result))
		if isinstance(result,list):
			if not empty(path):
				raise Exception('El nombre de nodo (path) indicado es una lista: ' + path)

			if not empty(selIndex) :
				logger.debug('recuperando nodo indice: ' + str(selIndex))
				try:
					node = result[selIndex]
					logger.debug('Recuperando indice:')
					node = result[selIndex]
					#nodo de la lista ya ha sido seleccionado
					if not empty(path):
						if path not in result:
							logger.error('El nodo no existe en la lista')
							raise Exception('El nodo no existe en la lista: ' + path)
						node = result[path]

					if not empty(query):
						r = createProgram(query)
						logger.debug(r)
						node = executeQuery(r,node, select )

					result = node
					continue
				except (IndexError,KeyError) as e:
					if isinstance(node,list):
						logger.error('Index ' + str(selIndex) + ' does not exitis in dataset')
					else:
						logger.error('The node is not a List or Array, you can not use idex here')
						logger.error(node.keys())
					quit()
			elif empty(selIndex) and not empty(query):
				r = createProgram(query)
				logger.debug(r)
				node = executeQuery(r,result, select )
				result = node
				continue

		else:
			#Excepciones
			if path not in result:
				logger.debug(path)
				logger.debug(result)
				logger.warning('nodo no encontrado:' + path)
				return {}

			node = result[path]  if not isinstance(result,list) else result #se trae el nodo
			logger.debug(type(node))
			#logger.debug(node)
			if not empty(selIndex):
				node = node[selIndex]

			if not empty(query):  
				logger.debug('Query')
				r = createProgram(query)
				logger.debug(r)
				node = executeQuery(r,node, select )
			elif not empty(select): #nodeQuery['select'] is not None:
				if isinstance(node,list):
					temp = []
					list(map( lambda item :  [ temp.append({ k: v }) for k,v in item.items() if k in select ], node ))
					node = temp
				elif isinstance(node,dict):
					node =[ { k : v } for k,v in node.items() if k in select ]

			result = node

		
	return result


def jsonquery(filename, path, _print = True):
	#validation = re.compile(r'(/)*(/{0,1}\w+)*(\[\d+[:{1}\d+]*\])*(/{0,1}\[s*[@\s\w=!<>\'"]+\s*\])*(\{[\w+"\',]+\})*')
	data = ''
	if True:#validation.fullmatch(path):
		with open(filename,'r') as f:
			data = json.load(f)
			res = processPath(data,path)
			if _print:
				pp.pprint(res)
			return res
	else:
		raise Exception('Invalid Synax: ' + path)

def jsonquery(jsonData, path):
	data = json.loads(jsonData)
	res = processPath(data,path)
	return res
	

class JsonQuery(object):
	def __init__(self,jsonText, debug = logging.ERROR):
		#logging.basicConfig(level=debug)

		self.jsonData = jsonText

	def execute(self,query='/'):
		self._dataset = json.loads(self.jsonData)
		return processPath(self._dataset,query)



#print( extractIndexs('[@id=="0001"]'))



