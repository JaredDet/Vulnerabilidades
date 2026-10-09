ORG ?= django

.PHONY: pipeline miner analyze publish serve clone codeql sbom grype dataset

# pipeline runs the three stages in order. analyze does not depend on miner,
# so it can use the committed Django evidence when no Miner output exists.
pipeline:
	$(MAKE) miner
	$(MAKE) analyze
	$(MAKE) publish

miner:
	bash scripts/miner.sh run --organization "$(ORG)"

analyze:
	bash scripts/run-analyzer.sh "$(ORG)"

publish:
	bash scripts/publish-visualizer.sh

serve: publish
	npm start --prefix visualizer -- --host 0.0.0.0 --port 4200

clone:
	bash scripts/miner.sh clone-repositories --organization "$(ORG)"

codeql:
	bash scripts/miner.sh analyze-code --organization "$(ORG)"

sbom:
	bash scripts/miner.sh generate-sbom --organization "$(ORG)"

grype:
	bash scripts/miner.sh scan-dependency-vulnerabilities --organization "$(ORG)"

dataset:
	bash scripts/miner.sh generate-dataset --organization "$(ORG)"
