# MyCloud

Free ICloud replacement

## How to use
App and API must be run on devices using the same network.

### App


### API
#### Run API:
mac/linux
```
./run.sh
```
windows
```
.\run.ps1
```
#### First time running API:
- Must have python installed
- create .env file with three variables:
```
SECRET_KEY=change-this-to-a-long-random-string
PORT=3000
PHOTO_STORAGE_PATH=CHANGE/to/PATH/you/WANT/to/SAVE/PHOTOS
```
- On the first run, you will be prompted to create a user and password to be used in the application. Once that has successfully been completed, the ip and port will log, which will need to be inputted into the application's server input.


