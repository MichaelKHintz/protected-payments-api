# One EC2 instance running k3s. No inbound rules at all: you reach it through SSM Session Manager.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnet" "node" {
  vpc_id            = data.aws_vpc.default.id
  availability_zone = "${var.region}a"
  default_for_az    = true
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_security_group" "node" {
  name        = "${var.name}-node"
  description = "k3s node: no inbound, outbound HTTP and HTTPS only"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "HTTPS: SSM, KMS, Okta, Claude API, container registries"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "HTTP: Ubuntu package mirrors"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "node" {
  name = "${var.name}-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# The node's own role can only talk to SSM. It has no KMS access, so even a pod that
# reached the instance metadata service would get nothing useful.
resource "aws_iam_role_policy_attachment" "node_ssm" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "node" {
  name = "${var.name}-node"
  role = aws_iam_role.node.name
}

resource "aws_instance" "node" {
  #checkov:skip=CKV_AWS_88:Public IP is for outbound traffic only (no NAT gateway in this lab); the security group allows no inbound.
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnet.node.id
  vpc_security_group_ids      = [aws_security_group.node.id]
  iam_instance_profile        = aws_iam_instance_profile.node.name
  associate_public_ip_address = true
  user_data                   = templatefile("${path.module}/k3s-install.sh.tftpl", { k3s_version = var.k3s_version })
  user_data_replace_on_change = true
  ebs_optimized               = true
  monitoring                  = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1          # pods sit one network hop away, so they can't get an IMDS token
  }

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "${var.name}-k3s" }
}

# A fixed public IP, so the KMS key policy can say "only from this address".
resource "aws_eip" "node" {
  domain   = "vpc"
  instance = aws_instance.node.id
  tags     = { Name = "${var.name}-egress" }
}

output "instance_id" {
  description = "Use with: aws ssm start-session --target <instance_id>"
  value       = aws_instance.node.id
}

output "node_egress_ip" {
  description = "Public IP the KMS key policies trust (pods leave the node through it)"
  value       = aws_eip.node.public_ip
}
