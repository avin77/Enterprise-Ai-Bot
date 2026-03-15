#!/usr/bin/env pwsh
.\scripts\aws-bootstrap.ps1 `
  -Mode deploy `
  -AwsRegion ap-south-1 `
  -AppName voice-bot-mvp `
  -ImageTag latest `
  -ContainerPort 8000 `
  -Cpu 256 `
  -Memory 512 `
  -DesiredCount 1 `
  -SubnetIds 'subnet-082abd89b1dd232ff' `
  -SecurityGroupIds 'sg-00b852a49de5258a0' `
  -DeployService
