# Waterfall ordering comparison (synthetic leads, mock providers, n=300, seed=7)

| ordering | rows | total cost | cost/row | cost/filled field | fields filled | calls |
|---|---|---|---|---|---|---|
| cheap_first | 295 | 238.8 | 0.8095 | 0.1724 | 1385 | 2520 |
| premium_first | 295 | 313.69 | 1.0634 | 0.2265 | 1385 | 1244 |
| conditional_icp | 295 | 96.35 | 0.3266 | 0.0836 | 1153 | 1673 |


Fill rate by field

| ordering | company_size | tech_stack | title | email | phone |
|---|---|---|---|---|---|
| cheap_first | 98% | 96% | 99% | 98% | 79% |
| premium_first | 98% | 96% | 99% | 98% | 79% |
| conditional_icp | 98% | 96% | 96% | 77% | 24% |


Average confidence of filled fields

| ordering | company_size | tech_stack | title | email | phone |
|---|---|---|---|---|---|
| cheap_first | 0.867 | 0.843 | 0.963 | 0.878 | 0.868 |
| premium_first | 0.931 | 0.866 | 0.981 | 0.934 | 0.89 |
| conditional_icp | 0.867 | 0.843 | 0.955 | 0.772 | 0.86 |
