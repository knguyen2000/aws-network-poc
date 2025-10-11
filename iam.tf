resource "random_id" "iam" {
  byte_length = 3
}

# Role with unique name each run
resource "aws_iam_role" "ec2_ssm_role" {
  name_prefix = "ec2-ssm-role-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

# Attach AWS managed SSM core (lets the instance register with SSM)
resource "aws_iam_role_policy_attachment" "ssm_core_attach" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Inline policy: READ scripts + WRITE results under your prefix
resource "aws_iam_role_policy" "s3_results_rw" {
  name = "s3-results-rw"
  role = aws_iam_role.ec2_ssm_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      # List only within the desired prefix
      {
        Sid      = "ListPrefix",
        Effect   = "Allow",
        Action   = ["s3:ListBucket"],
        Resource = "arn:aws:s3:::${aws_s3_bucket.results.bucket}",
        Condition = {
          StringLike = {
            "s3:prefix": ["${var.results_prefix}*"]
          }
        }
      },
      # Read scripts + write CSVs under the prefix
      {
        Sid      = "ObjectsRW",
        Effect   = "Allow",
        Action   = ["s3:GetObject", "s3:PutObject"],
        Resource = "arn:aws:s3:::${aws_s3_bucket.results.bucket}/${var.results_prefix}*"
      }
    ]
  })
}

# Instance profile with unique name each run
resource "aws_iam_instance_profile" "ec2_ssm_profile" {
  name_prefix = "ec2-ssm-profile-"
  role        = aws_iam_role.ec2_ssm_role.name
}
