provider "alicloud" {
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
}

resource "alicloud_vpc" "main" {
  name       = "tair_vpc"
  cidr_block = "172.16.0.0/16"
}

resource "alicloud_vswitch" "main" {
  vpc_id     = alicloud_vpc.main.id
  cidr_block = "172.16.0.0/24"
  zone_id    = var.zone_id
}

resource "alicloud_security_group" "main" {
  name   = "tair_sg"
  vpc_id = alicloud_vpc.main.id
}

resource "alicloud_security_group_rule" "allow_all" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "internet"
  policy            = "accept"
  port_range        = "6379/6379"
  priority          = 1
  security_group_id = alicloud_security_group.main.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_instance" "main" {
  instance_name        = "tair_ecs"
  instance_type        = "ecs.g5.large"
  security_groups      = [alicloud_security_group.main.id]
  vswitch_id           = alicloud_vswitch.main.id
  image_id             = "ubuntu_20_04_x64_20G_alibase_20210420.vhd"
  internet_charge_type = "PayByTraffic"
  instance_charge_type = "PostPaid"
  internet_max_bandwidth_out = 50
  password             = var.ecs_password
}

resource "alicloud_kvstore_instance" "tair" {
  instance_name       = "tair_instance"
  instance_class      = "tair.rdb.1g"
  vswitch_id          = alicloud_vswitch.main.id
  security_group_id   = alicloud_security_group.main.id
  instance_type       = "tair_rdb"
  engine_version      = "5.0"
  zone_id             = var.zone_id
  vpc_id              = alicloud_vpc.main.id
  auto_renew          = true
  charge_type         = "PostPaid"
}

output "ecs_instance_id" {
  value = alicloud_instance.main.id
}

output "tair_instance_id" {
  value = alicloud_kvstore_instance.tair.id
}

output "tair_instance_connection_string" {
  value = alicloud_kvstore_instance.tair.connection_string
}

output "tair_instance_port" {
  value = alicloud_kvstore_instance.tair.port
}
