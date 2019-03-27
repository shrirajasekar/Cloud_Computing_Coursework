from flask import Flask,Response, render_template, redirect, url_for, request, session, flash , jsonify
from flask_hashing import Hashing
import json,uuid
from cassandra.cluster import Cluster
from flask_cassandra import CassandraCluster
from functools import wraps
import requests
from twython import Twython
import pandas as pd
import socket

app = Flask(__name__,instance_relative_config=True)
cassandra = CassandraCluster()
hashing = Hashing(app)
app.config.from_pyfile('config.py')
app.config['CASSANDRA_NODES'] = ['localhost']  			#Change localhost to cassandra if deploying on Google cloud
app.secret_key = app.config['SECRET_KEY'] 				#Needed for https
python_tweets = Twython(app.config['TWITTER_CONSUMER_KEY'],app.config['TWITTER_CONSUMER_SECRET'])		#Use of Twitter as External API
tweets={}

def login_required(f):									#Annotation for prevention of access to content without a logged in session
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)

        else:
            flash('You need to login first.')
            return redirect(url_for('login'))
    return wrap

def role_based_access_control_admin(f):					#Annotation for role based access control 
    @wraps(f)
    def wrap(*args, **kwargs):
        print('Verifying role')
        print(session['role'])
        if 'role' in session and session['role'] == "admin":
            print("Authorized")
            return f(*args, **kwargs)

        else:
            print("Not Authorized")
            flash('You are not authorized to perform this action!.')
            return redirect(url_for('login'))
    return wrap

def role_based_access_control_manager(f):				#Annotation for role based access control
    @wraps(f)
    def wrap(*args, **kwargs):
        print('Verifying role')
        print(session['role'])
        if 'role' in session and (session['role'] == "manager" or session['role'] == "admin"):
            print("Authorized")
            return f(*args, **kwargs)

        else:
            print("Not Authorized")
            flash('You are not authorized to perform this action!.')
            return redirect(url_for('login'))
    return wrap

@app.route('/')											#Default route to Welcome page
def welcome():
    return render_template('welcome_page.html')  

@app.route('/search_twitter', methods=['GET', 'POST'])	#Route to External API to get Top 10 trending tweets based on a key word - Response - HTML
@login_required
def search_twitter():    
    query = {'q': request.form['keyword'],  
        'result_type': 'popular',
        'count': 10,
        'lang': 'en',
        }
    dict_ = {'text': [], 'favorite_count': [], 'profile_img_url': [], 'name': [],'url':[]}  
    for status in python_tweets.search(**query)['statuses']:  
        if not status['entities']['urls']:
            print("https://twitter.com/")
            dict_['url'].append("https://twitter.com/")
        else:
            print(status['entities']['urls'][0]['url'])
            dict_['url'].append(status['entities']['urls'][0]['url'])
        dict_['profile_img_url'].append(status['user']['profile_image_url'])
        dict_['text'].append(status['text'])
        dict_['name'].append(status['user']['name'])
        dict_['favorite_count'].append(status['favorite_count'])

    df = pd.DataFrame(dict_)  
    df.sort_values(by='favorite_count', inplace=True, ascending=False)  
    tweets = df.head(10).to_json(orient='records')
    dict_data = json.dumps(dict_)
    data = json.loads(dict_data)
    strHTM = "<h1> Top Tweets on : "+ request.form['keyword'].capitalize() +" </h1> <br> <table style = 'border: 1px solid black'>"
    for i in range(0,10):
        strHTM = strHTM + "<tr style ='border: 1px solid black'><td style ='border: 1px solid #dddddd'>"
        strHTM =  strHTM +str(i+1)+"</td><td style ='border: 1px solid #dddddd'>"
        strHTM =  strHTM +"<img src = "+data["profile_img_url"][i]+">"+"</td><td style ='border: 1px solid #dddddd'>"
        strHTM =  strHTM +"<a href = " +data["url"][i]+">"+data["text"][i]+"</a>"+"</td>"+"</tr>"
    strHTM = strHTM + "</table>"
    return strHTM

@app.route('/add_todo', methods=['GET', 'POST'])		#Internal API to add a task to the Database - Response - JSON with HATEOAS
@login_required
def add_todo():
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        task_name = request.form['task_name']
        task_description = request.form['task_description']
        task_priority = request.form['task_priority']
        task_start = request.form['task_start']
        task_end = request.form['task_end']
        task_difficulty = request.form['task_difficulty']
        task_assignee = request.form['task_assignee']
        subtasks_names = request.form['subtasks_names']
        subtasks_descriptions = request.form['subtasks_descriptions']
        subtasks_difficulties = request.form['subtasks_difficulties']
        subtasks_refs = request.form['subtasks_refs']
        subtasks_assignees = request.form['subtasks_assignees']
        id = str(uuid.uuid4())
        task_cql = "INSERT INTO todo.tasks(id,name,description,priority,difficulty,start,end,assignee) VALUES("+id+",'"+nullTostr(task_name.replace("'","''"))+"','"+nullTostr(task_description.replace("'","''"))+"','"+nullTostr(task_priority.replace("'","''"))+"','"+nullTostr(task_difficulty.replace("'","''"))+"','"+nullTostr(task_start.replace("'","''"))+"','"+nullTostr(task_end.replace("'","''"))+"','"+nullTostr(task_assignee.replace("'","''"))+"');"   
        print(task_cql)
        session.execute(task_cql)
        
        for i,s in enumerate(subtasks_names.split('|')):
            sub_tasks_cql = "INSERT INTO todo.sub_tasks(id,task_id,name,description,difficulty,ref,assignee) VALUES(UUID()"+",'"+id+"','"+nullTostr(s.replace("'","''"))+"','"+nullTostr(subtasks_descriptions.split('|')[i].replace("'","''"))+"','"+nullTostr(subtasks_difficulties.split('|')[i].replace("'","''"))+"','"+nullTostr(subtasks_refs.split('|')[i].replace("'","''"))+"','"+nullTostr(subtasks_assignees.split('|')[i].replace("'","''"))+"')"   
            print(s)
            session.execute(sub_tasks_cql)
            
        result = "{  \"success\": true,\n   \"status\":\"200\",\n   \"payload\":[{\"message"+":\"Task '" + task_name + "' added Successfully!\"}"+"],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_all_tasks\" \n },{ \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_task_details_by_id<"+str(id)+"\" \n },{ \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/delete_task_by_id<"+str(id)+"\" \n },{ \n \"rel\" : \"child\",\n \"href\": \""+ "/rest/get_all_sub_tasks\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        return Response (result, status = 200, mimetype = 'application/json')
        res="Task '" + task_name + "' added Successfully!"
        result = res
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result
    
@app.route('/delete_all_tasks', methods=['GET', 'POST'])				#Internal API to delete a task - Response - JSON with HATEOAS
@login_required
def delete_all_tasks():
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        tcql = "TRUNCATE TABLE tasks"
        session.execute(tcql)
        scql = "TRUNCATE TABLE sub_tasks"
        session.execute(scql)
        result = "{  \"success\": true,\n   \"status\":\"200\",\n   \"payload\":[{\"message"+":\"Deleted all tasks and corresponding sub-tasks successfully!\"}"+"],\n\"links\": [ { \n \"rel\" : \"child\",\n \"href\": \""+ "/dashboard\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (result, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result
    



@app.route("/get_all_tasks")											#Internal API to get all tasks from the database - Response - HTML
@login_required
def get_tasks():
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM tasks"
        r = list (session.execute(cql))
        print(len(r))
        res_htm = "<h1> Tasks to-do : </h1><ol>"
        for i,row in enumerate(r,0): 
            res_htm = res_htm +"<li><a href= /get_task_by_id<"+str(row.id)+">"+str(row.name)+"</a>&nbsp;&nbsp;&nbsp;&nbsp;"+"   - &nbsp;&nbsp;  Click Task ID for rest call to get task details (with HATEOAS)    - &nbsp;&nbsp;&nbsp;&nbsp;<a href = /rest/get_task_details_by_id<"+str(row.id)+">"+str(row.id)+"</a>&emsp;&emsp;&emsp;<a href = /rest/delete_task_by_id<"+str(row.id)+">Delete Task</a></li>"
        res_htm = res_htm+"</ol>"
        result = res_htm
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route("/get_task_by_id<id>")										#Internal API to get details of a task by its ID - Response - HTML
@login_required
def get_task_by_id(id):
    try:
        id=id.replace("<","")
        id=id.replace(">","")
        session = cassandra.connect()
        session.set_keyspace("todo")
        print(id)
        cql = "SELECT * FROM sub_tasks where task_id = '"+str(id)+"' ALLOW FILTERING"
        r = list (session.execute(cql))
        print(len(r))
        res_htm = "<h1>Task Details</h1><h2> Sub Tasks to perform : </h2><table><tr style ='border: 1px solid black'><th style ='border: 1px solid #dddddd'>Sequence Number</th><th style ='border: 1px solid #dddddd'>Sub-TaskName</th><th style ='border: 1px solid #dddddd'>Assignee</th><th style ='border: 1px solid #dddddd'>Role</th><th style ='border: 1px solid #dddddd'>Action</th></tr>"
        for i,row in enumerate(r,0): 
            u_cql = "SELECT * FROM users where id = "+str(row.assignee)
            u = list (session.execute(u_cql))
            res_htm = res_htm +"<tr><td style ='border: 1px solid #dddddd'>"+str(i+1)+"</td><td style ='border: 1px solid #dddddd'><a href =/get_sub_task_by_id<"+str(row.id)+">"+str(row.name)+"</a></td><td style ='border: 1px solid #dddddd'>"+str(u[0].name).capitalize()+"</td><td style ='border: 1px solid #dddddd'>"+str(u[0].role).capitalize()+"</td><td style ='border: 1px solid #dddddd'><a href=\\rest\delete_sub_task_by_id<"+str(row.id)+">Delete</a></td></tr>"
        res_htm = res_htm+"</ol>"
        result = res_htm
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route("/get_sub_task_by_id<id>")									#Internal API to get a sub-task by its ID - Response - HTML
@login_required
def get_sub_task_by_id(id):
    try:
        id = id.replace("<","")
        id=id.replace(">","")
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM sub_tasks where id = "+id
        r = list (session.execute(cql))
        res_htm = "<h1> Sub Task Details : </h1><br><h2>Click on Sub-Task ID for REST call (with HATEOAS implementation) </h2><table><tr style ='border: 1px solid black'><th style ='border: 1px solid #dddddd'>Sub-Task ID</th><th style ='border: 1px solid #dddddd'>Name</th><th style ='border: 1px solid #dddddd'>Description</th><th style ='border: 1px solid #dddddd'>Difficulty</th><th style ='border: 1px solid #dddddd'>Assignee</th><th style ='border: 1px solid #dddddd'>Role</th><th style ='border: 1px solid #dddddd'>References</th><th style ='border: 1px solid #dddddd'>Connected to Task</th></tr>"
        for i,row in enumerate(r,0): 
            t_cql = "SELECT * FROM tasks where id = "+str(row.task_id)
            t = list (session.execute(t_cql))        
            u_cql = "SELECT * FROM users where id = "+str(row.assignee)
            u = list (session.execute(u_cql))
            res_htm = res_htm + "<tr><td style ='border: 1px solid #dddddd'><a href = /rest/get_sub_task_details_by_id<"+str(row.id)+">"+str(row.id)+"</a></td><td style ='border: 1px solid #dddddd'>"+str(row.name).capitalize()+"</td><td style ='border: 1px solid #dddddd'>"+str(row.description)+"</td><td style ='border: 1px solid #dddddd'>"+str(row.difficulty)+"</td><td style ='border: 1px solid #dddddd'>"+str(u[0].name).capitalize()+"</td><td style ='border: 1px solid #dddddd'>"+str(u[0].role).capitalize()+"</td><td style ='border: 1px solid #dddddd'><a href = "+str(row.ref)+">"+str(row.ref)+"</a></td><td style ='border: 1px solid #dddddd'><a href= /get_task_by_id<"+str(row.task_id)+">"+str(t[0].name).capitalize()+"</a></td></tr>"
        res_htm = res_htm+"</table>"
        result = res_htm
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route('/add_worker', methods=['GET', 'POST'])						#Internal API to add a new employee -  - Response - JSON with HATEOAS
@login_required
@role_based_access_control_admin
def add_worker():
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        name = request.form['name']
        role = request.form['role']   
        idcql = "SELECT MAX(id) as id FROM users "
        idres = session.execute(idcql)
        print(idres[0].id)
        id = idres[0].id + 1
        print(id)
        worker_cql = "INSERT INTO todo.users(id,name,role) VALUES("+str(id)+",'"+nullTostr(name.replace("'","''"))+"','"+nullTostr(role.replace("'","''"))+"');"   
        print(worker_cql)
        session.execute(worker_cql)      
        result = "{  \"success\": true,\n   \"status\":\"200\",\n   \"payload\":[{\"message"+":\"Employee '" + name + "' with role '"+ role+"' added Successfully!\"}"+"],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_all_workers\" \n },{ \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_worker_by_id<"+str(id)+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result =  Response (result, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result
    
#------------------- REST implementation with HATEOAS ----------------

@app.route("/rest/get_all_tasks")								# REST implementation to get all tasks - Response - JSON with HATEOAS
@login_required
def get_all_tasks_rest():
    result = ""
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM tasks"
        r = list (session.execute(cql))        
        res = "{ \"success\": true,\n\"payload\":["

        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"priority\": \""+str(row.priority)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"start\": \""+str(row.start)+"\", \"end\": \""+str(row.end)+"\"}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"priority\": \""+str(row.priority)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"start\": \""+str(row.start)+"\", \"end\": \""+str(row.end)+"\"},"                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"child\",\n \"href\": \""+ "/rest/get_all_sub_tasks\" \n },{ \n \"rel\" : \"child\",\n \"href\": \""+ "/rest/get_sub_task_by_id<339610a6-7b04-4590-826c-4cbaed1c02c2\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route("/rest/get_task_details_by_id<id>")							#REST implementation to get task details by ID - Response - JSON with HATEOAS
@login_required
def get_task_details_by_id_rest(id):
    id = id.replace("<","")
    id=id.replace(">","")
    result = ""
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM tasks where id = "+id
        r = list (session.execute(cql))        
        res = "{ \"success\": true,\n\"payload\":["

        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"priority\": \""+str(row.priority)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"start\": \""+str(row.start)+"\", \"end\": \""+str(row.end)+"\"}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"priority\": \""+str(row.priority)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"start\": \""+str(row.start)+"\", \"end\": \""+str(row.end)+"\"},"                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"child\",\n \"href\": \""+ "/rest/get_all_sub_tasks\" \n },{ \n \"rel\" : \"child\",\n \"href\": \""+ "/rest/get_sub_task_by_id<"+id+"\" \n },{ \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/delete_task_by_id<"+id+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result


@app.route('/rest/delete_task_by_id<id>', methods=['GET', 'POST'])		#REST implementation to delete a task - Response - JSON with HATEOAS
@login_required
def delete_task_by_id(id):
    try:
        id=id.replace("<","")
        id=id.replace(">","")
        print(id)
        session = cassandra.connect()
        session.set_keyspace("todo")
        namecql = "SELECT * FROM tasks where id = "+id
        tnameres = session.execute(namecql)
        tname = tnameres[0].name
        tcql = "DELETE FROM tasks where id = "+id
        print(tcql)
        session.execute(tcql)    
        scql = "SELECT * FROM sub_tasks where task_id='"+id+"' ALLOW FILTERING"
        print(scql)
        listOfSubTasks = session.execute(scql)
        for row in listOfSubTasks:
            deleteSubTaskcql = "DELETE FROM sub_tasks where id="+str(row.id)
            print(deleteSubTaskcql)
            session.execute(deleteSubTaskcql)
        result = "{  \"success\": true,\n   \"status\":\"200\",\n   \"payload\":[{\"message"+":\"Deleted task '"+ tname +"' and corresponding sub-tasks!\"}"+"],\n\"links\": [ { \n \"rel\" : \"child\",\n \"href\": \""+ "/rest/get_all_sub_tasks\" \n },{ \n \"rel\" : \"child\",\n \"href\": \""+ "/rest/get_sub_task_by_id<"+id+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result =  Response (result, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result



@app.route("/rest/get_all_sub_tasks")					#REST implementation to get all sub tasks - Response - JSON with HATEOAS
@login_required
def get_all_sub_tasks_rest():
    result = ""
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM sub_tasks"
        r = list (session.execute(cql))
        res = "{ \"success\": true,\n\"payload\":["
        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"ref\": \""+str(row.ref)+"\", \"task_id\": \""+str(row.task_id)+"\"}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"ref\": \""+str(row.ref)+"\", \"task_id\": \""+str(row.task_id)+"\"},"                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/get_sub_task_by_id< bae50b56-19a8-4ece-92ae-c5eeb2dc81a2\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route("/rest/get_sub_task_details_by_id<id>")		#REST implementation to get all sub tasks by ID - Response - JSON with HATEOAS
@login_required
def get_sub_task_details_rest(id):
    id=id.replace("<","")
    id=id.replace(">","")
    print(id)
    result = ""
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM sub_tasks where id = "+id
        print(cql)
        r = list (session.execute(cql))
        res = "{ \"success\": true,\n\"payload\":["
        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"ref\": \""+str(row.ref)+"\", \"task_id\": \""+str(row.task_id)+"\"}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"ref\": \""+str(row.ref)+"\", \"task_id\": \""+str(row.task_id)+"\"},"                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_sub_task_details_by_id< "+id+"\" \n },{ \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/delete_sub_task_by_id< "+id+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result


@app.route("/rest/get_sub_tasks_by_task_id<id>")		#REST implementation to get details of a sub task by its ID  - Response - JSON with HATEOAS
@login_required
def get_sub_tasks_by_task_id_rest(id):
    id=id.replace("<","")
    id=id.replace(">","")
    print(id)
    result = ""
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM sub_tasks where task_id = '"+str(id)+"' ALLOW FILTERING"
        r = list (session.execute(cql))
        res = "{ \"success\": true,\n\"payload\":["
        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"ref\": \""+str(row.ref)+"\", \"task_id\": \""+str(row.task_id)+"\"}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"assignee\": \""+str(row.assignee)+"\", \"description\": \""+str(row.description)+"\", \"difficulty\": \""+str(row.difficulty)+"\", \"name\": \""+str(row.name)+"\", \"ref\": \""+str(row.ref)+"\", \"task_id\": \""+str(row.task_id)+"\"},"                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/get_sub_task_by_id< bae50b56-19a8-4ece-92ae-c5eeb2dc81a2\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route('/rest/delete_sub_task_by_id<id>', methods=['GET', 'POST'])			#REST implementation to delete a sub task by its ID - Response - JSON with HATEOAS
@login_required
def delete_sub_task_by_id(id):
    try:
        id=id.replace("<","")
        id=id.replace(">","")
        print(id)
        session = cassandra.connect()
        session.set_keyspace("todo")
        namecql = "SELECT * FROM sub_tasks where id = "+id
        snameres = session.execute(namecql)
        sname = snameres[0].name
        cql = "DELETE FROM sub_tasks where id = "+id
        print(cql)
        session.execute(cql)    
        result = "{  \"success\": true,\n   \"status\":\"200\",\n   \"payload\":[{\"message\""+":\"Deleted sub-task '"+ sname +"'\","+"],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_all_sub_tasks\" \n },{ \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_sub_task_details_by_id<"+id+"\" \n },{ \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/delete_sub_task_by_id<"+id+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (result, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result
#------------ Workers/Employees ----------- 

@app.route("/rest/get_all_workers")					#REST implementation to get a list of all employees  - Response - JSON with HATEOAS - accessible only by manager and admin
@login_required
@role_based_access_control_manager
def get_all_workers_rest():
    result = ""
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM users"
        r = list (session.execute(cql))
        res = "{ \"success\": true,\n\"payload\":["
        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"name\": \""+str(row.name)+"\", \"role\": \""+str(row.role)+"\"\n}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"name\": \""+str(row.name)+"\", \"role\": \""+str(row.role)+"\"},"                                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_worker_by_id< "+str(row.id)+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route("/rest/get_all_users")			#REST implementation to get a list of signed up users - Response - JSON with HATEOAS - Accessible only by admin
@login_required
@role_based_access_control_admin
def get_all_users_rest():
    result = ""
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM login"
        r = list (session.execute(cql))
        res = "{ \"success\": true,\n\"payload\":["
        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"name\": \""+str(row.uname)+"\", \"role\": \""+str(row.role)+"\"\n}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"name\": \""+str(row.uname)+"\", \"role\": \""+str(row.role)+"\"},"                                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_user_by_id< "+str(row.id)+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\"}"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route("/get_all_workers")
@role_based_access_control_manager		#Internal API to get all employees - Response - HTML - Accessible only by manager and admin
@login_required
def get_all_workers():
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM users"
        r = list (session.execute(cql))
        print(len(r))
        res_htm = "<h1> List of Employees : </h1><table><tr style ='border: 1px solid black'><th style ='border: 1px solid #dddddd'>EMP ID</th><th style ='border: 1px solid #dddddd'>Name</th><th style ='border: 1px solid #dddddd'>Role</th><th style ='border: 1px solid #dddddd'>Action</th></tr>"
        for i,row in enumerate(r,0): 
            res_htm = res_htm +"<tr><td style ='border: 1px solid #dddddd'>"+str(row.id)+"</td><td style ='border: 1px solid #dddddd'><a href =/rest/get_worker_by_id<"+str(row.id)+">"+str(row.name).capitalize()+"</a></td><td style ='border: 1px solid #dddddd'>"+str(row.role).capitalize()+"</td><td style ='border: 1px solid #dddddd'><a href=/rest/delete_worker_by_id<"+str(row.id)+">Delete</a></td></tr>"
        res_htm = res_htm+"</table>"
        print(res_htm)
        result = res_htm
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result

@app.route("/get_all_users")		#Internal API to get a list of all signed up users - Response - HTML - Accessible only by the admin
@login_required
@role_based_access_control_admin
def get_all_users():
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM login"
        r = list (session.execute(cql))
        print(len(r))
        res_htm = "<h1> List of Application users : </h1><table><tr style ='border: 1px solid black'><th style ='border: 1px solid #dddddd'>User ID</th><th style ='border: 1px solid #dddddd'>Name</th><th style ='border: 1px solid #dddddd'>Role</th><th style ='border: 1px solid #dddddd'>Action</th></tr>"
        for i,row in enumerate(r,0): 
            res_htm = res_htm +"<tr><td style ='border: 1px solid #dddddd'>"+str(row.id)+"</td><td style ='border: 1px solid #dddddd'><a href =/rest/get_user_by_id<"+str(row.id)+">"+str(row.uname).capitalize()+"</a></td><td style ='border: 1px solid #dddddd'>"+str(row.role).capitalize()+"</td><td style ='border: 1px solid #dddddd'><a href=/rest/delete_user_by_id<"+str(row.id)+">Delete</a></td></tr>"
        res_htm = res_htm+"</ol>"
        result = res_htm
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result


@app.route("/rest/get_worker_by_id<id>")					#REST implementation to get a list of all employees  - Response - JSON with HATEOAS
@login_required
def get_worker_by_id(id):    
    try:
        id=id.replace("<","")
        id=id.replace(">","")
        print(id)
        result = ""
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM users where id = "+id
        r = list (session.execute(cql))
        res = "{ \"success\": true,\n\"payload\":["
        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"user name\": \""+str(row.name)+"\", \"role\": \""+str(row.role)+"\"\n}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"user name\": \""+str(row.name)+"\", \"role\": \""+str(row.role)+"\"},"                                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/delete_worker_by_id< "+str(row.id)+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result


@app.route("/rest/get_user_by_id<id>")			#REST implementation to get details of an user by ID  - Response - JSON with HATEOAS
@login_required
@role_based_access_control_admin
def get_user_by_id(id):
    try:
        id=id.replace("<","")
        id=id.replace(">","")
        print(id)
        result = ""
        session = cassandra.connect()
        session.set_keyspace("todo")
        cql = "SELECT * FROM login where id = "+id
        r = list (session.execute(cql))
        res = "{ \"success\": true,\n\"payload\":["
        for i,row in enumerate(r,0):              
            if((i+1)==len(r)):
                res = res +  "{\"id\": \""+str(row.id)+"\", \"user name\": \""+str(row.uname)+"\", \"role\": \""+str(row.role)+"\"\n}"                
            else:
                res = res +  "{\"id\": \""+str(row.id)+"\", \"user name\": \""+str(row.uname)+"\", \"role\": \""+str(row.role)+"\"},"                                
        res = res + "],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/delete_user_by_id< "+str(row.id)+"\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (res, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result


@app.route('/rest/delete_worker_by_id<id>', methods=['GET', 'POST'])		#REST implementation to delete a worker by ID  - Response - JSON with HATEOAS
@login_required	
@role_based_access_control_admin
def delete_worker_by_id(id):
    try:
        id=id.replace("<","")
        id=id.replace(">","")
        print(id)
        session = cassandra.connect()
        session.set_keyspace("todo")
        namecql = "SELECT * FROM users where id = "+id
        snameres = session.execute(namecql)
        sname = snameres[0].name
        cql = "DELETE FROM users where id = "+id
        print(cql)
        session.execute(cql)    
        result = "{  \"success\": true,\n   \"status\":\"200\",\n   \"payload\":[{\"message\""+":\"Deleted worker'"+ sname +"'\"}"+"],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+"/rest/get_all_workers\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (result, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result


@app.route('/rest/delete_user_by_id<id>', methods=['GET', 'POST'])			#REST implementation to delete a signed up user's account by ID - Respon		se - JSON with HATEOAS - accessible only by admin
@login_required
@role_based_access_control_admin
def delete_user_by_id(id):
    try:
        id=id.replace("<","")
        id=id.replace(">","")
        print(id)
        session = cassandra.connect()
        session.set_keyspace("todo")
        namecql = "SELECT * FROM login where id = "+id
        snameres = session.execute(namecql)
        sname = snameres[0].uname
        cql = "DELETE FROM login where id = "+id
        print(cql)
        session.execute(cql)    
        result = "{  \"success\": true,\n   \"status\":\"200\",\n   \"payload\":[{\"message\""+":\"Deleted user'"+ sname +"'\"}"+"],\n\"links\": [ { \n \"rel\" : \"self\",\n \"href\": \""+ "/rest/get_all_users\" \n }],\"host-IP\" :\""+request.environ.get('HTTP_X_REAL_IP', request.remote_addr)+"\" }"
        result = Response (result, status = 200, mimetype = 'application/json')
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result


@app.route('/dashboard')										#Route to Dashboard
@login_required
def dashboard():
    return render_template('dashboard.html')  
		
@app.route('/login', methods=['GET', 'POST'])					#Route to Login page
def login():
    try:
        error = None
        sess = cassandra.connect()
        sess.set_keyspace("todo")
        print("logiin")
        pwd = ""
        role= ""
        if request.method == 'POST':
            pwdcql = "SELECT * from login where uname = '" + request.form['username'] +"' ALLOW FILTERING"
            r =  list(sess.execute(pwdcql))
            if len(r)>0:
                pwd = r[0].pwd
                role = r[0].role
            if len(r)==0:
                print("No such user!")
                error = "No such user"
            if  not(pwd == hashing.hash_value(request.form['password'], salt=app.config['SALT'])):		#SALTED HASH using SHA256
                error = 'Invalid Credentials. Please try again. Why not sign up if you dont have an account?'
            else:
                session['logged_in'] = True
                session['role'] = role
                print(session['role'])
                return redirect(url_for('dashboard'))
        return render_template('login.html', error=error)
    except Exception as e:
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result
    

@app.route('/signup', methods=['GET', 'POST'])				#Route to sign up page - new users get 'user' role by default
def signup():
    try:
        session = cassandra.connect()
        session.set_keyspace("todo")
        error = None
        if request.method == 'POST':
            pw_hash = hashing.hash_value(request.form['password'], salt=app.config['SALT'])
            cql = "INSERT INTO login (id,pwd,uname,role) VALUES(UUID(),'"+pw_hash+"','"+request.form['username']+"','user')"
            print(cql)
            r = list (session.execute(cql))
            error = "Login Created Successfully!"
            return redirect(url_for('login'))
        return render_template('signup.html', error=error)
    except Exception as e:         
        result = Response ("{  \n   \"success\" : \"false\", \n   \"code\": \""+type(e).__name__+"\",\n   \"message\" : \""+ str(e)+"\"\n}",status=500,mimetype = 'application/json')
    return result
		
@app.route('/logout')										#Route to Log out page
@login_required
def logout():
    session.pop('logged_in', None)
    flash('You were logged out.')
    return redirect(url_for('welcome'))

def nullTostr(s):
    if s is None:
        return ''
    return str(s)


if __name__ == '__main__':
   app.run(debug=True, ssl_context=('cert/server.crt', 'cert/server.key'))