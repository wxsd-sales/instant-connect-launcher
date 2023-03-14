# Instant Connect Launcher

Includes a calendar/scheduling web based UI for Instant Connect meetings, and allows sending meeting links via sms and email.

Welcome to our WXSD DEMO Repo! <!-- Keep this here --> 
<!-- Keep the following here -->  
 *_Everything included is for demo and Proof of Concept purposes only. Your use of the site is solely at your own risk. This site may contain links to third party content, which we do not warrant, endorse, or assume liability for. These demos are for Cisco Webex usecases, but are not Official Cisco Webex Branded demos._
**A GUI Scheduling Utility for Instant Connect**

<a href="https://instant-connect-launcher.wbx.ninja/"><strong>View Demo</strong></a>
·
<a href="https://github.com/WXSD-Sales/instant-connect-launcher/issues"><strong>Report Bug</strong></a>
·
<a href="https://github.com/WXSD-Sales/instant-connect-launcher/issues"><strong>Request Feature</strong></a>



## Overview
[![Instant Connect Scheduler Video](https://user-images.githubusercontent.com/19175490/194949324-3c4eae5f-73d6-4d3e-8c97-01331198eaab.png)](https://app.vidcast.io/share/c781f1c8-d258-488e-9d3a-41d279a310b3)

Server Requirements:
1. python version >= 3.8
2. pip install modules.

Alternatively, you can install **docker** and build/run this as a container using the provided Dockerfile.

## Setup

### Server Side Setup
1. Clone this repository
2. Rename ```sample.env``` to ```.env```, and edit the values in .env *(be sure to keep string values between the quotes)*
3. Navigate inside the cloned directory in your terminal, then run:
```
RUN pip install tornado==4.5.2
RUN pip install requests
RUN pip install requests-toolbelt
RUN pip install boto3
RUN pip install aws-requests-auth
RUN pip install icalendar
```

## Support

Please reach out to the WXSD team at [wxsd@external.cisco.com](mailto:wxsd@external.cisco.com?cc=<your_cec>@cisco.com&subject=RepoName).
