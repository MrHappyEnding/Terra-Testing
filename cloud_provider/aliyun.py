import time
import uuid
import subprocess
import yaml
from alibabacloud_r_kvstore20150101 import models as r_kvstore_20150101_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_vpc20160428.client import Client as Vpc20160428Client

class InstanceInfo:
    def __init__(self, instance_id="", instance_name="", instance_account="", instance_password="", region_id="", vpc_id="", vsw_id="", private_ip=""):
        self.instance_id = instance_id
        self.instance_name = instance_name
        self.instance_account = instance_account
        self.instance_password = instance_password
        self.region_id = region_id
        self.vpc_id = vpc_id
        self.vsw_id = vsw_id
        self.private_ip = private_ip

class AliyunResourceManager:
    def __init__(self, config):
        self.config = config
        self.kv_client = None
        self.runtime = util_models.RuntimeOptions()

    def create_kv_client(self):
        try:
            config = open_api_models.Config(
                access_key_id=self.config['Database']['Tair']['access_key'],
                access_key_secret=self.config['Database']['Tair']['access_key_secret']
            )
            config.endpoint = 'r-kvstore.aliyuncs.com'
            self.kv_client = r_kvstore_20150101_models.Client(config)
        except Exception as e:
            print(f"Failed to create KV client: {e}")
            raise

    def create_vpc_client(self, region):
        try:
            config = open_api_models.Config(
                access_key_id=self.config['Database']['Tair']['access_key'],
                access_key_secret=self.config['Database']['Tair']['access_key_secret']
            )
            config.endpoint = f'vpc.cn-{region}.aliyuncs.com'
            return Vpc20160428Client(config)
        except Exception as e:
            print(f"Failed to create VPC client: {e}")
            raise

    def purchase_redis_instance(self):
        try:
            self.create_kv_client()
            region_id = self.config['Database']['Tair']['region_id']
            zone_id = self.config['Database']['Tair']['zone_id']
            vpc_id, vsw_id = self.create_vpc(region_id, zone_id)

            create_tair_instance_request = r_kvstore_20150101_models.CreateTairInstanceRequest(
                region_id=region_id,
                instance_class='tair.rdb.1g',
                zone_id=zone_id,
                vpc_id=vpc_id,
                v_switch_id=vsw_id,
                auto_use_coupon='true',
                charge_type='PostPaid',
                instance_type='tair_rdb',
                auto_pay=True,
            )
            tair_info = self.kv_client.create_tair_instance_with_options(create_tair_instance_request, self.runtime).to_map()
            instance_id = tair_info['body']['InstanceId']
            private_ip = tair_info['body']['PrivateIp']
            print(f"Successfully created Tair instance with ID: {instance_id}")
            return InstanceInfo(instance_id=instance_id, region_id=region_id, vpc_id=vpc_id, vsw_id=vsw_id, private_ip=private_ip)
        except Exception as e:
            print(f"Failed to purchase Redis instance: {e}")
            raise

    def create_vpc(self, region_id, zone_id):
        try:
            client = self.create_vpc_client(region_id.split('-')[1])
            create_vpc_request = r_kvstore_20150101_models.CreateVpcRequest(
                region_id=region_id,
                vpc_name=f"tair_cts_vpc_{str(uuid.uuid4())[:5]}",
                cidr_block='172.16.0.0/24'
            )
            vpc_info = client.create_vpc_with_options(create_vpc_request, self.runtime).to_map()
            vpc_id = vpc_info['body']['VpcId']
            print(f"Successfully created VPC with ID: {vpc_id}")

            create_vswitch_request = r_kvstore_20150101_models.CreateVSwitchRequest(
                region_id=region_id,
                vpc_id=vpc_id,
                cidr_block='172.16.0.0/24',
                zone_id=zone_id,
                v_switch_name=f"tair_cts_vsw_{str(uuid.uuid4())[:5]}",
            )
            vsw_info = client.create_vswitch_with_options(create_vswitch_request, self.runtime).to_map()
            vsw_id = vsw_info['body']['VSwitchId']
            print(f"Successfully created VSwitch with ID: {vsw_id}")

            return vpc_id, vsw_id
        except Exception as e:
            print(f"Failed to create VPC or VSwitch: {e}")
            raise

    def configure_redis_instance(self, instance_infos):
        try:
            print("开始配置阿里云 Tair 实例")
            modify_security_ips_request = r_kvstore_20150101_models.ModifySecurityIpsRequest(
                instance_id=instance_infos.instance_id,
                security_ips='10.0.0.0/8'  # 仅允许内部 IP 访问
            )
            self.kv_client.modify_security_ips_with_options(modify_security_ips_request, self.runtime)
            time.sleep(60)

            reset_account_password_request = r_kvstore_20150101_models.ResetAccountPasswordRequest(
                instance_id=instance_infos.instance_id,
                account_name=instance_infos.instance_id,
                account_password='tair_test'
            )
            self.kv_client.reset_account_password_with_options(reset_account_password_request, self.runtime)
            time.sleep(5)

            instance_infos.instance_account = instance_infos.instance_id
            instance_infos.instance_password = 'tair_test'
            print("Tair configure successfully")
        except Exception as e:
            print(f"Failed to configure Redis instance: {e}")
            raise

    def check_instance_status(self, instance_id, region_id):
        describe_instances_overview_request = r_kvstore_20150101_models.DescribeInstancesOverviewRequest(
            region_id=region_id,
            instance_ids=instance_id,
        )
        try:
            instance_status = ""
            while instance_status != "Normal":
                instance_desc = self.kv_client.describe_instances_overview_with_options(
                    describe_instances_overview_request,
                    self.runtime
                ).to_map()
                instance_status = instance_desc['body']['Instances'][0]['InstanceStatus']
                print(f"instance status：{instance_status}")
                time.sleep(10)
        except Exception as e:
            print(f"Failed to check instance status: {e}")
            raise

    def run_compatibility_tests(self, instance_infos, testfile, show_failed):
        print("start Tair compatibility-test")
        self.check_instance_status(instance_infos.instance_id, instance_infos.region_id)

        command = [
            "python3",
            "redis_compatibility_test.py",
            "--testfile", testfile,
            "--show-failed",
            "--host", instance_infos.private_ip,
            "--port", "6379",
            "--password", instance_infos.instance_password
        ]

        try:
            with open("test_result.txt", "w") as output_file:
                result = subprocess.run(command, stdout=output_file, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    print("test is running successfully")
                    print("saved results in test_result.txt")
                else:
                    print("test failed!")
                    print("stderr:", result.stderr)
        except Exception as e:
            print(f"Failed to run compatibility tests: {e}")
            raise

    def cleanup_resources(self, instance_infos):
        try:
            print("start to release Tair instance...")
            delete_instance_request = r_kvstore_20150101_models.DeleteInstanceRequest(
                instance_id=instance_infos.instance_id
            )
            self.kv_client.delete_instance_with_options(delete_instance_request, self.runtime)
            print(f"Deleted Tair instance with ID: {instance_infos.instance_id}")

            time.sleep(300)

            print("start to delete VPC switchboard...")
            region_single = instance_infos.region_id.split('-')[1]
            vpc_client = self.create_vpc_client(region_single)
            delete_vswitch_request = r_kvstore_20160428_models.DeleteVSwitchRequest(
                region_id=instance_infos.region_id,
                v_switch_id=instance_infos.vsw_id,
            )
            vpc_client.delete_vswitch_with_options(delete_vswitch_request, self.runtime)
            print(f"Deleted VSwitch with ID: {instance_infos.vsw_id}")

            time.sleep(10)

            print("start to delete VPC...")
            delete_vpc_request = r_kvstore_20160428_models.DeleteVpcRequest(
                region_id=instance_infos.region_id,
                vpc_id=instance_infos.vpc_id,
                force_delete=True
            )
            vpc_client.delete_vpc_with_options(delete_vpc_request, self.runtime)
            print(f"Deleted VPC with ID: {instance_infos.vpc_id}")

            print("delete Aliyun Redis instance successfully")
        except Exception as e:
            print(f"Failed to clean up resources: {e}")
            raise

def parse_args():
    parser = argparse.ArgumentParser(description="Manage Alibaba Cloud resources and run Redis compatibility tests")
    parser.add_argument("--config", required=True, help="Path to the config file")
    parser.add_argument("--testfile", required=True, help="Path to the test file")
    parser.add_argument("--show-failed", action='store_true', help="Show details of failed tests")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)

        manager = AliyunResourceManager(config)
        instance_info = manager.purchase_redis_instance()
        manager.configure_redis_instance(instance_info)
        manager.run_compatibility_tests(instance_info, args.testfile, args.show_failed)
        manager.cleanup_resources(instance_info)
    except Exception as e:
        print(f"An error occurred: {e}")
