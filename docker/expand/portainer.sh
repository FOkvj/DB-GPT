docker service create \
  --name portainer \
  --publish published=9443,target=9443 \
  --publish published=9000,target=9000 \
  --publish published=8000,target=8000 \
  --replicas=1 \
  --constraint 'node.role == manager' \
  --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock \
  --mount type=volume,src=portainer_data,dst=/data \
  portainer/portainer-ce:latest
