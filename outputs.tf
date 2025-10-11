output "server_private_ip" {
  value = aws_instance.server.private_ip
}

output "client_public_ip" {
  value = aws_instance.client.public_ip
}

output "client_name_tag" {
  value = "network-test-client"
}

output "results_bucket_name" {
  value = aws_s3_bucket.results.bucket
}
