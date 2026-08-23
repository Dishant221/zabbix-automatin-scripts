logs-ci-patch-ketello-details
logs-ci-patch-ketello-details-histroy

logs-ci-patch-kernal-care-details
logs-ci-patch-kernal-care-details-histroy




logs-ci-patch-aws-ssm-details-history
logs-ci-patch-aws-ssm-details


logs-ci-patch-desktop-central-details-history
logs-ci-patch-desktop-central-details

logs-ci-patch-vm-coverage
logs-ci-patch-vm-coverage-history


ilm policy : Observability_aggregate_gold

ci-patch-vm-coverage-history-template
ci-patch-aws-ssm-details-history-template
ci-patch-ketello-details-history-template
ci-patch-desktop-central-details-history-template
ci-patch-kernal-care-details-histroy-template


ilm policy Cloud-Insights_silver
ci-patch-aws-ssm-details-template
ci-patch-vm-coverage-template
ci-patch-kernal-care-details-template
ci-patch-ketello-details-template
ci-patch-desktop-central-details-template


{
  "index": {
    "lifecycle": {
      "name": "Observability_aggregate_gold"
    },
    "mode": "standard"
  }
}