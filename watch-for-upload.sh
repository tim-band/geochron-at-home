#!/bin/bash

echo "$(basename -- $0) watching user upload"
inotifywait -m -e create -e moved_to /code/user_upload/ |
while read path action file; do 
  if [ $file == "do_commit" ]; then
    current_time=$(date "+%Y.%m.%d-%H.%M.%S")
    python upload_projects.py --settings=geochron.settings > /code/user_upload/user_upload.$current_time.log 2>&1 ;
    rm /code/user_upload/do_commit
  fi; 
done
