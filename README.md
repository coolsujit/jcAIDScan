# jcAIDScan
An automated scanner for installed Java Card packages (Windows version)

[![MIT licensed](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/petrs/jcAIDScan/blob/master/LICENSE)

JCVM consists of library packages as per specification by the Java Card Forum. Some of these packages are mandatory to be implemented in the Java Card, and some of the packages are optional. The decision for implementation of the optional packages lies with the manufacturer of the particular smart card family with Java Card platform. jcAIDScan tool is developed to detect the supported packages, classes and methods implemented in the examined Java Card.

# Pre-Requisites:

1. Python 3.0.5 or higher

2. Notepad++ or Python IDE (to edit the code if needed)

# Detailed usage:

1. Clone/ Download the "jcAIDScan" project.

2. If the smart card inserted needs "-emv" option, then before starting the tool, edit the jcAIDScan.py file as under:

    (a) Comment - GP_AUTH_FLAG = ''
  
    (b) Uncomment -  # GP_AUTH_FLAG = '--emv'
  
3. By default, the detection tool scans for all classes (0 to 255) for every detected package. It is possible to give the single range or multiple ranges of the classes to be detected. Edit the jcAIDScan.py file's main() function to give the range of classes as per requirement.

4. Start the detection tool by using the following command in the command prompt:
python jcAIDScan.py

5. Please read carefully the initial important information displayed after starting the tool before proceeeding with the detection process.

6. As the next step, the tool lists already installed applets in the smart card. Please proceed only if the installed applets are listed properly.

7. Please provide the name of the smart card and wait for the detection process to be finished. After the detection process is completed, CSV file containing the detected packages and classes is created (nameofthecard_ATR.csv).

# Troubleshooting:
1. Reader not detected: 
        Check the reader connectivity with the PC. If needed, reinstall the drivers.
2. Applet list not displayed: 
        (a) Check whether "-emv" option is required for the smart card. If yes then perform step 2 given in usage section.
        (b) Re-insert the smart card
