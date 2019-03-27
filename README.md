# Cloud_Computing_Coursework
RESTful application using python and flask for Cloud computing coursework.

# Introduction to App - 'All in one Dashboard'
This is a 'Task management' application that allows users to view,delete,assign tasks and sub-tasks. 

# Implementations

The following implementations are made as per mini-project specification

1. REST based application Interface (The application has more than 15 APIs performing GET and POST actions with HATEOAS implementation communicating with Cassandra Database)
2. Interaction with external REST services. (The application uses Twitter API to get top-10 tweets on a topic of user's choice)
3. Use of on an external Cloud database for persisting information. (The application uses cassandra deployed on gcloud cluster for storing persistent information for the application)
4. Support for cloud scalability, deployment in a container environment. (The steps for deploying the application can be found in later sections of this README file. Also a demonstration of deployment and cloud scalability will be presented to the course lecturer as instructed)
5. Cloud security awareness. (External API key, Password of users and other confidential information are abstracted by including them in config.py file or the database)

The above implementations are to be considered for 6/10 points and the below add-ons are implemented for 6 more points

1. Demonstration of load balancing and scaling of the application (e.g. kubernetes based load balancing, as well as Cassandra ring scaling)
    - *Testing load balancing* - The application provides many REST APIs starting with the route /rest/. All the responses have HATEOAS       implementation for navigation using APIs alone without the support of UI (However a basic HTML UI is also designed and is in              place). In those responses a field for *Host-IP* is included purposely to show the effect of load-balancing. 
       It can be seen that the same API's response will be having different  *Host-IP* values for everytime its called.
    - *Testing Cassandra ring scaling* - This will be demonstrated and the effect will be discussed in one of the lab sessions. The             scaling command is:
        **kubectl scale rc cassandra --replicas=n**
        *Where 'n' is the number of cassandra replicas*
    
2. Implemented cloud security measures.
    - The application is served over "HTTPS"
    - Hash based authentication - The user's passwords are hashed using sha256 and stored in the Database, instead of storing plaintext           password
    - Implementing user accounts and access management - The application has  types of users - admin, manager, user. The users are given         privileges based on their roles. The contents they can view or the actions they can perform are driven by their roles
    - Securing the database with role-based policies - Unauthorized users or users with insufficient privileges can't access content or           delete any records in the database
    
3. Any of the app components have a non-trivial purpose.

    - Request followup orchestration using HATEOAS - All the REST API responses from the application have HATEOAS implemented to present       to the user with urls for other REST APIs that might interest the user for navigation through API responses or Request followup         orchestration.
    
    - Complex database implementation including data schema design, or substantial write operations - The application uses 4 tables           (tasks,sub_tasks,users,login) and their relationship is as follows
                  1. Task -------< Sub-task             (One - Many relationship based on task Id. A task can have multiple sub-task)
                  2. Task ------- Assignee/user/worker  (One Task is assigned to one employee/worker)
                  3. Sub-task ------- Assignee/user/worker  (One Sub-Task is assigned to one employee/worker)
            The login table contains the application users credentials and also their roles based on which their privileges and access               will be managed upon login.
 
 # Setup and Installation
 
 ***Follow the below commands and instructions to deploy the application in a Single node***
 
 **Requirements**
        Python, Cassandra Database, Browser and all the modules mentioned in requirements.txt file
    
        1. Download the project from GIT and navigate to python_flask_rest_app 
        2. Make sure you have cassandra database installed and running with necessary keyspace and tables,users are created (refer to                    misc/cassandra-queries.txt)
        2. Activate python environment and run python app.py
        3. The application should run on localhost:5000
        
  
 ***Follow the below commands and instructions to deploy the application in a gcloud cluster***
 
 **Requirements**
        Python, Cassandra Database, GCloud, Kubernetes and all the modules mentioned in requirements.txt file
    
        1. Login to Gcloud platform and open Gcloud shell
        2. Export Project ID using 
              export PROJECT_ID="$(gcloud config get-value project -q)"
        3. Create a new folder and clone the application source files
        4. Create a n node container cluster the command
              gcloud container clusters create cassandra --num-nodes=n --machine-type "n1-standard-2" --zone  europe-west2-a
          (You can chose any name for the cluster, any machine type or zone)
          It will take some time for the cluster to be provisioned
        4. Navigate to the folder and 
        Download the project from GIT and navigate to python_flask_rest_app 
        5. Inside the project folder there are 3 yml files cassandra-peer-service.yml, cassandra-service.yml, cassandra-replication-                controller.yml
           Each file is for creating a service like replication, intra-node communication. Run the following commands to create these              services
               kubectl create -f cassandra-peer-service.yml
               kubectl create -f cassandra-service.yml
               kubectl create -f cassandra-replication-controller.yml
        6. Create necessary keyspace and tables and users (refer to misc/cassandra-queries.txt)
        7. Build a docker image 
               docker build -t gcr.io/${PROJECT_ID}/miniproj-app:v1 .
        8. Push the image to gcr.io
               docker push gcr.io/${PROJECT_ID}/miniproj-app:v1
        9. Run the application by pulling the image
               kubectl run miniproj-app --image=gcr.io/${PROJECT_ID}/miniproj-app:v1 --port 8080
        10. Expose port for port mapping
               kubectl expose deployment miniproj-app --type=LoadBalancer --port 80 --target-port 8080
        11. Steps 9 and 10 can be replaced by a shorthand method to create deployment and loadbalancer by running kubectl create command             on deployment.yml and loadbalancer.yml using the below commands
               kubectl create -f deployment.yml
               kubectl create -f loadbalancer.yml
        12. Run kubectl get services to find the external IP of the load balancer 
        13. Visit the external IP using a browser, each consecutive request will be served by a different machine in the cluster which               can be verified by the HOST-IP field in API responses.
        
# Adding a new Task inside the Dash board
    
        Each Task can have any number of sub-tasks but each parameter (eg:assignee,difficulty,priority) should be correspondingly assigned to each subtask.
        ***The different values for each sub-task are seperated by a '|' symbol. The idea was to keep the UI as simple as possible. The user can implement a much more user friendly UI if intended.***

*All the errors in the appliation are handling in such a way that no stack trace will be displayed in the browser under any circumstances*
    
    
