# Local Milter Project For Zimbra


### Descriptiton
Python3-based Local milter service,

This service integrates with zimbra email server and dynamically insert a succinct disclaimer into body of external emails.

![image](https://github.com/7pill/LocalMilter/assets/82153776/67ee9291-922a-4261-a778-40f149432e15)

-----------------
### Install requirement package
For ubuntu 18 or later
```
apt install python3-milter supervisor python3-pip
pip3 install pymilter
```

Older ubuntu,
```
apt-get install python-dev libmilter-dev python3-pip
pip3 install pymilter
```

-----------------
### Setup supervisord to load milterscript at startup
```
chmod +x disclaimer_milter.py
cp ./conf/local_milter.conf /etc/supervisor/conf.d
systemctl restart supervisor
systemctl enable supervisor
```

In the config file, home directory of service was set to */opt/zimbra/LocalMilter*.

We can clone source on to */opt/zimbra* to make the config file work properly,

Or we can change the command option on the config file to match the source path.

Log file of service stored at */var/log/local-milter.log*

Default listening port of milter service is 9999.

Listening port can be change on *disclaimer_milter.py* file.

-----------------
### Setup zimbra milter to set our milter as an MTA
```
su - zimbra
zmprov ms `zmhostname` zimbraMtaSmtpdMilters inet:127.0.0.1:9999
zmprov ms `zmhostname` zimbraMtaNonSmtpdMilters inet:127.0.0.1:9999
zmprov ms `zmhostname` zimbraMilterServerEnabled TRUE
zmmtactl restart

#if no milter running on port 7026, we can set zimbra to use only our local milter
postconf -e 'smtpd_milters = inet:127.0.0.1:9999'
```

-----------------
### Customization
Disclaimer message can be update on *disclaimer_message.txt* and *disclaimer_message.html* file as our suite.

Add exception domain to skip the disclaimer message on *exception_domains.txt* file
(zmhostname of zimbra domain server should included).
