sudo docker build -t coursilium-backend:dev .
sudo docker rm test
sudo docker run -d --name test -p 80:80 coursilium-backend:dev