import shutil
import os
import subprocess
from shutil import copyfile
import time
import textwrap

# defaults
SCRIPT_VERSION = '0.1.1'
BASE_PATH = '.'  # base path where script looks for templates an store output files

FORCE_UNINSTALL = True  # if true, test applet will be always attempted to be removed. Set to False for faster testing
FORCE_NO_SAFETY_CHECK = False # if True, no user prompt for authentication verification is performed. Leave this as False

GP_BASIC_COMMAND = 'gp.exe'  # command which will start GlobalPlatformPro binary
GP_AUTH_FLAG = ''  # most of the card requires no additional authentication flag
# GP_AUTH_FLAG = '--emv'  # use of EMV key diversification is used (e.g., G&D cards)

AID_VERSION_MAP = {"000107A0000000620001": "2.1",  # java.lang
                   "000107A0000000620002": "2.2.0",  # java.io
                   "000107A0000000620003": "2.2.0",  # java.rmi
                   # javacard.framework
                   "000107A0000000620101": "2.1", "010107A0000000620101": "2.2.0", "020107A0000000620101": "2.2.1",
                   "030107A0000000620101": "2.2.2", "040107A0000000620101": "3.0.1", "050107A0000000620101": "3.0.4",
                   "060107A0000000620101": "3.0.5",
                   # javacard.framework.service
                   "000108A000000062010101": "2.2.0",
                   # javacard.security
                   "000107A0000000620102": "2.1", "010107A0000000620102": "2.1.1", "020107A0000000620102": "2.2.1",
                   "030107A0000000620102": "2.2.2", "040107A0000000620102": "3.0.1", "050107A0000000620102": "3.0.4",
                   "060107A0000000620102": "3.0.5",
                   # javacardx.crypto
                   "000107A0000000620201": "2.1", "010107A0000000620201": "2.1.1", "020107A0000000620201": "2.2.1",
                   "030107A0000000620201": "2.2.2", "040107A0000000620201": "3.0.1", "050107A0000000620201": "3.0.4",
                   "060107A0000000620201": "3.0.5",
                   # javacardx.biometry (starting directly from version 1.2 - previous versions all from 2.2.2)
                   "000107A0000000620202": "2.2.2", "010107A0000000620202": "2.2.2", "020107A0000000620202": "2.2.2",
                   "030107A0000000620202": "3.0.5",
                   "000107A0000000620203": "2.2.2",  # javacardx.external
                   "000107A0000000620204": "3.0.5",  # javacardx.biometry1toN
                   "000107A0000000620205": "3.0.5",  # javacardx.security
                   # javacardx.framework.util
                   "000108A000000062020801": "2.2.2", "010108A000000062020801": "3.0.5",
                   "000109A00000006202080101": "2.2.2",  # javacardx.framework.util.intx
                   "000108A000000062020802": "2.2.2",  # javacardx.framework.math
                   "000108A000000062020803": "2.2.2",  # javacardx.framework.tlv
                   "000108A000000062020804": "3.0.4",  # javacardx.framework.string
                   "000107A0000000620209": "2.2.2",  # javacardx.apdu
                   "000108A000000062020901": "3.0.5",  # javacardx.apdu.util
                   }

AID_NAME_MAP = {"A0000000620001": "java.lang",
                "A0000000620002": "java.io",
                "A0000000620003": "java.rmi",
                "A0000000620101": "javacard.framework",
                "A000000062010101": "javacard.framework.service",
                "A0000000620102": "javacard.security",
                "A0000000620201": "javacardx.crypto",
                "A0000000620202": "javacardx.biometry",
                "A0000000620203": "javacardx.external",
                "A0000000620204": "javacardx.biometry1toN",
                "A0000000620205": "javacardx.security",
                "A000000062020801": "javacardx.framework.util",
                "A00000006202080101":"javacardx.framework.util.intx",
                "A000000062020802":"javacardx.framework.math",
                "A000000062020803":"javacardx.framework.tlv",
                "A000000062020804":"javacardx.framework.string",
                "A0000000620209": "javacardx.apdu",
                "A000000062020901": "javacardx.apdu.util",
                "A00000015100": "org.globalplatform"
                }


class PackageAID:
    aid = []
    major = 0
    minor = 0

    def __init__(self, aid, major, minor):
        self.aid = aid
        self.major = major
        self.minor = minor

    def get_readable_string(self):
        return "{0} v{1}.{2} {3}".format(self.get_well_known_name(), self.major, self.minor, self.get_aid_hex())

    def get_length(self):
        return len(self.aid) + 1 + 1 + 1

    def serialize(self):
        aid_str = ''.join('{:02X}'.format(a) for a in self.aid)
        # one package format: package_major package_minor package_len package_AID
        serialized = '{:02X}{:02X}{:02X}{}'.format(self.minor, self.major, len(self.aid), aid_str)
        return serialized

    def get_aid_hex(self):
        return bytes(self.aid).hex()  # will be in lowercase

    def get_well_known_name(self):
        hex_aid = bytes(self.aid).hex().upper()
        if hex_aid in AID_NAME_MAP:
            return AID_NAME_MAP[hex_aid]
        else:
            return "unknown"

    def get_first_jcapi_version(self):
        hex_aid = bytes(self.aid).hex().upper()
        aid_with_version = "{0:02X}{1:02X}{2:02X}{3}".format(self.minor, self.major, len(self.aid), hex_aid)
        if aid_with_version in AID_VERSION_MAP:
            version = AID_VERSION_MAP[aid_with_version]
        else:
            version = "unknown"

        return version


class TestCfg:
    min_major = 1
    max_major = 1
    min_minor = 0
    max_minor = 1
    modified_ranges = []
    package_template = ""
    package_template_bytes = []

    def __init__(self, package_template, min_major, max_major, min_minor, max_minor, modified_range=None):
        self.min_major = min_major
        self.max_major = max_major
        self.min_minor = min_minor
        self.max_minor = max_minor
        self.modified_ranges = modified_range
        self.package_template = package_template
        self.package_template_bytes = bytearray(bytes.fromhex(package_template))

    def __repr__(self):
        modifiers_str = ""
        if self.modified_ranges:
            modifiers_str = ''.join('[{0}]=[{1:02X}-{2:02X}] '.format(a[0], a[1], a[2]) for a in self.modified_ranges)
        return 'MAJOR=[{0}-{1}], MINOR=[{2}-{3}], {4}, TEMPLATE={5}'.format(
            self.min_major, self.max_major, self.min_minor, self.max_minor, modifiers_str, self.package_template)

    @staticmethod
    def get_val_range(offset, modified_ranges, template_value):
        if modified_ranges:
            for range_modif in modified_ranges:
                if range_modif[0] == offset:
                    return range_modif[1], range_modif[2]

        # if no special range modifier found, then return byte from template
        return template_value, template_value


class CardInfo:
    card_name = ""
    atr = ""
    cplc = ""
    gp_i = ""

    def __init__(self, card_name, atr, cplc, gp_i):
        self.card_name = card_name
        self.atr = atr
        self.cplc = cplc
        self.gp_i = gp_i


javacard_framework = PackageAID(b'\xA0\x00\x00\x00\x62\x01\x01', 1, 0)
java_lang = PackageAID(b'\xA0\x00\x00\x00\x62\x00\x01', 1, 0)
package_template = b'\xA0\x00\x00\x00\x62\x01\x01'


class AIDScanner:
    base_path = BASE_PATH
    force_uninstall = FORCE_UNINSTALL  # if true, test applet will be always attempted to be removed. Set to False for faster testing
    force_no_safety_check = FORCE_NO_SAFETY_CHECK  # if True, no user prompt for authentication verification is performed. Leave this as False
    gp_basic_command = GP_BASIC_COMMAND # command which will start GlobalPlatformPro binary
    gp_auth_flag = GP_AUTH_FLAG # most of the card requires no additional authentication flag, some requires '--emv'
    card_name = ""
    is_installed = True # if true, test applet is installed and will  be removed
    num_tests = 0 # number of executed tests (for performance measurements)

    def check_classtoken(self, package, uninstall, class_token):
        shutil.make_archive('test.cap', 'zip', '{0}\\template_class\\'.format(self.base_path))

        package_hex = package.serialize()

        # remove zip suffix
        os.remove('test.cap')
        os.rename('test.cap.zip', 'test.cap')
        # store used cap file
        copyfile('test.cap',
                 '{0}\\results\\test_{1}_class_{2:02X}.cap'.format(self.base_path, package_hex, int(class_token)))

        # (try to) uninstall previous applet if necessary/required
        if uninstall or self.force_uninstall:
            subprocess.run([self.gp_basic_command, self.gp_auth_flag, '--uninstall', 'test.cap'], stdout=subprocess.PIPE)

        # try to install test applet
        result = subprocess.run([self.gp_basic_command, self.gp_auth_flag, '--install', 'test.cap', '--d'],
                                stdout=subprocess.PIPE)
        result = result.stdout.decode("utf-8")
        # store gp result into log file

        f = open('{0}\\results\\{1}_class_{2:02X}.txt'.format(self.base_path, package_hex, int(class_token)), 'w')
        f.write(result)
        f.close()

        # heuristics to detect successful installation - log must contain error code 0x9000 followed by SCardEndTransaction
        # If installation fails, different error code is present
        if result.find('9000\r\nSCardEndTransaction()') != -1:
            return True
        else:
            return False

    def check_aid(self, import_section, package, uninstall):
        # save content of Import.cap into directory structure
        print(import_section)
        f = open('{0}\\template\\test\\javacard\\Import.cap'.format(self.base_path), 'wb')
        f.write(bytes.fromhex(import_section))
        f.close()

        # create new cap file by zip of directories
        shutil.make_archive('test.cap', 'zip', '{0}\\template\\'.format(self.base_path))

        package_hex = package.serialize()

        # remove zip suffix
        os.remove('test.cap')
        os.rename('test.cap.zip', 'test.cap')
        # store used cap file
        copyfile('test.cap', '{0}\\results\\test_{1}.cap'.format(self.base_path, package_hex))

        # (try to) uninstall previous applet if necessary/required
        if uninstall or self.force_uninstall:
            subprocess.run([self.gp_basic_command, self.gp_auth_flag, '--uninstall', 'test.cap'], stdout=subprocess.PIPE)

        # try to install test applet
        result = subprocess.run([self.gp_basic_command, self.gp_auth_flag, '--install', 'test.cap', '--d'], stdout=subprocess.PIPE)

        # store gp result into log file
        result = result.stdout.decode("utf-8")
        f = open('{0}\\results\\{1}.txt'.format(self.base_path, package_hex), 'w')
        f.write(result)
        f.close()

        # heuristics to detect successful installation - log must contain error code 0x9000 followed by SCardEndTransaction
        # If installation fails, different error code is present
        if result.find('9000\r\nSCardEndTransaction()') != -1:
            return True
        else:
            return False

    def format_import(self, packages_list):
        total_len = 1 # include count of number of packages
        for package in packages_list:
            total_len += package.get_length()

        # format of Import.cap: 04 00 len num_packages package1 package2 ... packageN
        import_section = '0400{:02x}{:02x}'.format(total_len, len(packages_list))

        # serialize all packages
        for package in packages_list:
            import_section += package.serialize()

        return import_section

    # In this function, test.cap is prepared using template from folder template_class
    # The class tokens are read from text file which are stored in class_files folder
    # For each classtoken, ConstantPool.cap file is changed and installation is checked
    def check_classes(self,import_section, package, uninstall, classes_supported_list):
        f = open('{0}\\template_class\\test\\javacard\\Import.cap'.format(self.base_path), 'wb')
        f.write(bytes.fromhex(import_section))
        f.close()

        file_name='{0}\\class_files\\{1}.txt'.format(self.base_path, package.serialize())
        if not os.path.exists(file_name):
            print("No Class details found for checking \n")
            return uninstall

        f = open(file_name, 'r')
        class_check = f.readlines()
        f.close()

        if len(class_check) <= 0:
            print("No Class details found for checking \n")
            return uninstall

        if len(class_check) > 0:
            f = open('{0}\\template_class\\test\\javacard\\ConstantPool.cap'.format(self.base_path), 'rb')
            hexdata = f.read().hex().upper()
            f.close()
            hex_array = bytearray(bytes.fromhex(hexdata))
            for class_item in class_check:
                # check installation for each class token no
                # Firstly check whether the Class is already checked or not.
                class_name, class_token = class_item.split(':')
                class_full_name = ''.join(['{0}', '.', '{1}']).format(package.get_well_known_name(), class_name)
                if len(classes_supported_list) > 0:
                    if any(class_full_name in included_classes for included_classes in classes_supported_list):
                        continue
                    else:
                        print(
                            "Checking for {0}; \t Class Token {1:02X}\n".format(package.serialize(), int(class_token)))
                        hex_array[43] = int(class_token)
                        f = open('{0}\\template_class\\test\\javacard\\ConstantPool.cap'.format(self.base_path), 'wb')
                        f.write(hex_array)
                        f.close()
                        uninstall = self.check_classtoken(package, uninstall, class_token)
                        if uninstall:
                            print("***Class Name {0}.{1} is Supported \n".format(package.get_well_known_name(),
                                                                                 class_name))
                            class_entry = ''.join(['{0}', '.', '{1}', ';', 'yes']).format(package.get_well_known_name(),
                                                                                          class_name)
                            classes_supported_list.append(class_entry)
                        else:
                            print("***Class Name {0}.{1} is Not Supported \n".format(package.get_well_known_name(),
                                                                                     class_name))
                            class_entry = ''.join(['{0}', '.', '{1}', ';', 'no']).format(package.get_well_known_name(),
                                                                                         class_name)
                            classes_supported_list.append(class_entry)
                else:
                    print("Checking for {0}; \t Class Token {1:02X}\n".format(package.serialize(), int(class_token)))
                    hex_array[43] = int(class_token)
                    f = open('{0}\\template_class\\test\\javacard\\ConstantPool.cap'.format(self.base_path), 'wb')
                    f.write(hex_array)
                    f.close()
                    uninstall = self.check_classtoken(package, uninstall, class_token)
                    if uninstall:
                        print("***Class Name {0}.{1} is Supported \n".format(package.get_well_known_name(), class_name))
                        class_entry = ''.join(['{0}', '.', '{1}', ';', 'yes']).format(package.get_well_known_name(),
                                                                                      class_name)
                        classes_supported_list.append(class_entry)
                    else:
                        print("***Class Name {0}.{1} is Not Supported \n".format(package.get_well_known_name(),
                                                                                 class_name))
                        class_entry = ''.join(['{0}', '.', '{1}', ';', 'no']).format(package.get_well_known_name(),
                                                                                     class_name)
                        classes_supported_list.append(class_entry)

        return uninstall

    def test_aid(self, tested_package_aid, supported_list, tested_list, classes_supported_list):
        imported_packages = []
        imported_packages.append(javacard_framework)
        #imported_packages.append(java_lang)  # do not import java_lang as default (some cards will then fail to load)
        imported_packages.append(tested_package_aid)

        import_content = self.format_import(imported_packages)

        if self.check_aid(import_content, tested_package_aid, self.is_installed):
            print(" ###########\n  {0} IS SUPPORTED\n ###########\n".format(tested_package_aid.get_readable_string()))
            supported_list.append(tested_package_aid)
            tested_list[tested_package_aid] = True
            self.is_installed = True
            # Class detection related change
            # The Package AID is supported now using check_classes function all the classes
            # belonging to this packages will be tested
            self.is_installed = self.check_classes(import_content, tested_package_aid, self.is_installed, classes_supported_list)
        else:
            print("   {0} v{1}.{2} is NOT supported ".format(tested_package_aid.get_aid_hex(), tested_package_aid.major,
                                                             tested_package_aid.minor))
            tested_list[tested_package_aid] = False
            self.is_installed = False

        return self.is_installed

    def print_supported(self, supported):
        print(" #################\n")
        if len(supported) > 0:
            for supported_aid in supported:
                print("{0} (since JC API {1})\n".format(supported_aid.get_readable_string(),
                                                        supported_aid.get_first_jcapi_version()))
        else:
            print("No items")
        print(" #################\n")


    def run_scan_recursive(self, modified_ranges_list, package_aid, major, minor, supported, tested, classes_supported_list):
        # recursive stop
        if len(modified_ranges_list) == 0:
            return

        # make local copy of modifiers list except first item
        local_modified_ranges_list = []
        local_modified_ranges_list[:] = modified_ranges_list[1:]

        # process first range and call recursively for the rest
        current_range = modified_ranges_list[0]
        offset = current_range[0]
        # compute actual range based on provided values
        start = current_range[1]
        stop = current_range[2]

        local_package_aid = bytearray(len(package_aid))
        local_package_aid[:] = package_aid
        for value in range(start, stop + 1):
            local_package_aid[offset] = value

            # check if already applied all modifiers
            if len(local_modified_ranges_list) == 0:
                #  if yes, then check prepared AID
                new_package = PackageAID(local_package_aid, major, minor)
                # test current package
                self.test_aid(new_package, supported, tested, classes_supported_list)
                self.num_tests += 1
            else:
                # if no, run additional recursion
                self.run_scan_recursive(local_modified_ranges_list, local_package_aid, major, minor, supported, tested, classes_supported_list)

        # print supported after iterating whole range
        self.print_supported(supported)


    def run_scan(self, cfg, supported, tested, classes_supported_list):
        print("################# BEGIN ###########################\n")
        print(cfg)
        print("###################################################\n")

        localtime = time.asctime(time.localtime(time.time()))
        print(localtime)

        # start performance measurements
        elapsed = -time.perf_counter()
        self.num_tests = 0

        self.is_installed = True  # assume that test applet was installed to call uninstall

        # check all possible values from specified ranges
        new_package_aid = bytearray(bytes.fromhex(cfg.package_template))
        for major in range(cfg.min_major, cfg.max_major + 1):
            self.print_supported(supported)
            print("############################################\n")
            print("MAJOR = {0:02X}".format(major))
            for minor in range(cfg.min_minor, cfg.max_minor + 1):
                self.print_supported(supported)
                print("###########################:#################\n")
                print("MAJOR = {0:02X}, MINOR = {1:02X}".format(major, minor))

                # Now recursively iterate via specified ranges (if provided)
                if cfg.modified_ranges:
                    self.run_scan_recursive(cfg.modified_ranges, new_package_aid, major, minor, supported, tested, classes_supported_list)
                else:
                    # nor modification ranges, just test package with current combination of major and minor version
                    new_package = PackageAID(new_package_aid, major, minor)
                    # test current package
                    self.test_aid(new_package, supported, tested, classes_supported_list)
                    self.num_tests += 1

        # end performance measurements
        elapsed += time.perf_counter()

        self.print_supported(supported)

        print("Elapsed time: {0:0.2f}s\nTesting speed: {1:0.2f} AIDs / min\n".format(elapsed, self.num_tests / (elapsed / 60)))

        print("################# END ###########################\n")
        print(cfg)
        print("#################################################\n")

    def scan_jc_api_305(self, card_info, supported, tested, classes_supported):
        MAX_MAJOR = 1
        ADDITIONAL_MINOR = 1
        # minor is tested with ADDITIONAL_MINOR additional values higher than expected from the given version of JC SDK).
        # If highest version is detected, additional inspection is necessary - suspicious (some cards ignore minor version)

        # intermediate results are saved after every tested package to preserve info even in case of card error

        self.run_scan(TestCfg("A0000000620001", 1, MAX_MAJOR, 0, 0 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A0000000620002", 1, MAX_MAJOR, 0, 0 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A0000000620003", 1, MAX_MAJOR, 0, 0 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)

        self.run_scan(TestCfg("A0000000620101", 1, MAX_MAJOR, 0, 6 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A000000062010101", 1, MAX_MAJOR, 0, 0 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A0000000620102", 1, MAX_MAJOR, 0, 6 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)

        self.run_scan(TestCfg("A0000000620201", 1, MAX_MAJOR, 0, 6 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A0000000620202", 1, MAX_MAJOR, 0, 3 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A0000000620203", 1, MAX_MAJOR, 0, 0 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A0000000620204", 1, MAX_MAJOR, 0, 0 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)
        self.run_scan(TestCfg("A0000000620205", 1, MAX_MAJOR, 0, 0 + ADDITIONAL_MINOR), supported, tested, classes_supported)
        self.save_scan(card_info, supported, tested, classes_supported)

        self.print_supported(supported)

    def get_card_info(self, card_name):
        if card_name == "":
            card_name = input("Please enter card name: ")

        result = subprocess.run([self.gp_basic_command, self.gp_auth_flag, '--i'], stdout=subprocess.PIPE)
        result_text = result.stdout.decode("utf-8")

        atr_before = "http://smartcard-atr.appspot.com/parse?ATR="
        pos = result_text.find(atr_before)
        end_pos = result_text.find("\n", pos)
        atr = result_text[pos + len(atr_before):end_pos]
        atr = atr.rstrip()

        cplc_before = "Card CPLC:"
        pos = result_text.find(cplc_before)
        cplc = result_text[pos + len(cplc_before):]
        cplc = cplc.rstrip()
        cplc = cplc.replace(":", ";")

        return CardInfo(card_name, atr, cplc, result_text)

    def save_scan(self, card_info, supported, tested, classes_supported):
        card_name = card_info.card_name.replace(' ', '_')
        file_name = "{0}_AIDSUPPORT_{1}.csv".format(card_name, card_info.atr)
        f = open('{0}\\{1}'.format(self.base_path, file_name), 'w')

        f.write("jcAIDScan version; {0}\n".format(SCRIPT_VERSION))
        f.write("Card ATR; {0}\n".format(card_info.atr))
        f.write("Card name; {0}\n".format(card_info.card_name))
        f.write("CPLC;;\n{0}\n\n".format(card_info.cplc))

        f.write("PACKAGE AID; MAJOR VERSION; MINOR VERSION; PACKAGE NAME; INTRODUCING JC API VERSION;\n")
        for aid in supported:
            f.write("{0}; {1}; {2}; {3}; {4}\n".format(aid.get_aid_hex(), aid.major, aid.minor, aid.get_well_known_name(),
                                                   aid.get_first_jcapi_version()))

        if tested:
            f.write("\n")
            f.write("FULL PACKAGE AID; IS SUPPORTED?; PACKAGE NAME WITH VERSION; \n")
            for aid in tested:
                f.write("{0}; \t{1}; \t{2};\n".format(aid.serialize(), "yes" if tested[aid] else "no", aid.get_readable_string()))

        f.write("\n")
        f.write("CLASS NAME; IS SUPPORTED; \n")
        for class_name in classes_supported:
            f.write("{0}\n".format(class_name))

        f.close()

    def prepare_for_testing(self):
        # restore default import section
        imported_packages = []
        imported_packages.append(javacard_framework)
        #imported_packages.append(java_lang)
        import_section = self.format_import(imported_packages)
        f = open('{0}\\template\\test\\javacard\\Import.cap'.format(self.base_path), 'wb')
        f.write(bytes.fromhex(import_section))
        f.close()

        # uninstall any previous installation of applet
        result = subprocess.run([self.gp_basic_command, self.gp_auth_flag, '--uninstall', 'test.cap'], stdout=subprocess.PIPE)
        result_text = result.stdout.decode("utf-8")
        self.is_installed = False

    def verify_gp_authentication(self):
        # Try to list applets on card then prompt user for confirmation
        info = "IMPORTANT: Supported package scanning will execute large number of OpenPlatform SCP " \
                            "authentications. If your GlobalPlatformPro tool is not setup properly and fails to " \
                            "authenticate, your card may be permanently blocked. This script will now execute one " \
                            "authentication to list installed applets. Check if everything is correct. If you will see " \
                            "any authentication error, do NOT continue. Also, do not remove your card from reader during "\
                            "the whole scanning process."
        print(textwrap.fill(info, 80))

        input("\nPress enter to continue...")
        print("Going to list applets, please wait...")

        result = subprocess.run([self.gp_basic_command, self.gp_auth_flag, '--list', '--d'], stdout=subprocess.PIPE)
        result_text = result.stdout.decode("utf-8")
        print(result_text)

        auth_result = input("Were applets listed with no error? (yes/no): ")
        if auth_result == "yes":
            return True
        else :
            return False

    def print_info(self):
        print("jcAIDScan v{0} tool for scanning supported JavaCard packages.\nCheck https://github.com/petrs/jcAIDScan/ "
              "for the newest version and documentation.\n2018, Petr Svenda\n".format(SCRIPT_VERSION))

        info = "WARNING: this is a research tool and expects that you understand what you are doing. Your card may be " \
               "permanently blocked in case of incorrect use."

        print(textwrap.fill(info, 80))

    def scan_jc_api_305_complete(self):

        self.print_info()
        # verify gp tool configuration + user prompt
        if not self.force_no_safety_check:
            if not self.verify_gp_authentication():
                return

        # restore template to good known state, uninstall applet etc.
        self.prepare_for_testing()

        # obtain card basic info
        card_info = self.get_card_info(self.card_name)

        # scan standard JC API
        supported = []
        classes_supported = []
        tested = {}
        elapsed = -time.perf_counter()
        self.scan_jc_api_305(card_info, supported, tested, classes_supported)
        elapsed += time.perf_counter()
        print("Complete test elapsed time: {0:0.2f}s\n".format(elapsed))
        # create file with results
        self.save_scan(card_info, supported, tested, classes_supported)


def main():
    app = AIDScanner()
    app.scan_jc_api_305_complete()

if __name__ == "__main__":
    main()
