# HubSpot deal properties (exported from the test portal)

Total: 208 properties - by type: number=73, datetime=44, enumeration=36, string=34, bool=17, object_coordinates=3, date=1

| name | label | type | fieldType | group | HubSpot-defined |
|---|---|---|---|---|---|
| `hs_analytics_latest_source` | Latest Traffic Source | enumeration | calculation_equation | analyticsinformation | True |
| `hs_analytics_latest_source_company` | Latest Traffic Source Company | enumeration | select | analyticsinformation | True |
| `hs_analytics_latest_source_contact` | Latest Traffic Source Contact | enumeration | select | analyticsinformation | True |
| `hs_analytics_latest_source_data_1` | Latest Traffic Source Data 1 | string | text | analyticsinformation | True |
| `hs_analytics_latest_source_data_1_company` | Latest Traffic Source Data 1 Company | string | text | analyticsinformation | True |
| `hs_analytics_latest_source_data_1_contact` | Latest Traffic Source Data 1 Contact | string | text | analyticsinformation | True |
| `hs_analytics_latest_source_data_2` | Latest Traffic Source Data 2 | string | text | analyticsinformation | True |
| `hs_analytics_latest_source_data_2_company` | Latest Traffic Source Data 2 Company | string | text | analyticsinformation | True |
| `hs_analytics_latest_source_data_2_contact` | Latest Traffic Source Data 2 Contact | string | text | analyticsinformation | True |
| `hs_analytics_latest_source_timestamp` | Latest Traffic Source Timestamp | datetime | number | analyticsinformation | True |
| `hs_analytics_latest_source_timestamp_company` | Latest Traffic Source Timestamp Company | datetime | date | analyticsinformation | True |
| `hs_analytics_latest_source_timestamp_contact` | Latest Traffic Source Timestamp Contact | datetime | date | analyticsinformation | True |
| `hs_analytics_source` | Original Traffic Source | enumeration | select | analyticsinformation | True |
| `hs_analytics_source_data_1` | Original Traffic Source Drill-Down 1 | string | text | analyticsinformation | True |
| `hs_analytics_source_data_2` | Original Traffic Source Drill-Down 2 | string | text | analyticsinformation | True |
| `closed_lost_reason` | Closed Lost Reason | string | textarea | deal_activity | True |
| `closed_won_reason` | Closed Won Reason | string | textarea | deal_activity | True |
| `dealstage` | Deal Stage | enumeration | radio | deal_activity | True |
| `engagements_last_meeting_booked` | Date of last meeting booked in meetings tool | datetime | date | deal_activity | True |
| `engagements_last_meeting_booked_campaign` | Campaign of last booking in meetings tool | string | text | deal_activity | True |
| `engagements_last_meeting_booked_medium` | Medium of last booking in meetings tool | string | text | deal_activity | True |
| `engagements_last_meeting_booked_source` | Source of last booking in meetings tool | string | text | deal_activity | True |
| `hs_associated_deal_registration_deal_type` | Associated Shared Deal Type | enumeration | select | deal_activity | True |
| `hs_associated_deal_registration_product_interests` | Associated Shared Deal Product Interests | enumeration | checkbox | deal_activity | True |
| `hs_deal_registration_mrr` | HubSpot Shared Deal MRR | number | number | deal_activity | True |
| `hs_deal_registration_mrr_currency_code` | HubSpot Shared Deal MRR Currency Code | enumeration | select | deal_activity | True |
| `hs_has_last_conversation_follow_ups` | Has Last Conversation Follow Ups | bool | calculation_equation | deal_activity | True |
| `hs_has_last_meeting_followups` | Has Last Meeting Follow Ups | bool | calculation_equation | deal_activity | True |
| `hs_is_active_shared_deal` | Is Active Shared Deal | bool | booleancheckbox | deal_activity | True |
| `hs_is_closed_lost` | Is closed lost | bool | calculation_equation | deal_activity | True |
| `hs_is_closed_won` | Is Closed Won | bool | calculation_equation | deal_activity | True |
| `hs_last_call_id_with_followups` | Last call ID with followups | number | number | deal_activity | True |
| `hs_last_conversation_with_followups_object_coordinates` | Last conversation with follow-ups | object_coordinates | text | deal_activity | True |
| `hs_last_email_with_followups_object_coordinates` | Last email with follow-ups | string | text | deal_activity | True |
| `hs_last_followup_timestamp` | Last follow-up timestamp | datetime | date | deal_activity | True |
| `hs_last_gs_shared_message` | Last GS Shared Message | datetime | calculation_rollup | deal_activity | True |
| `hs_last_meeting_id_with_followups` | Last meeting ID with followups | number | number | deal_activity | True |
| `hs_last_partner_shared_message_date` | Last Partner Shared Message Date | date | calculation_rollup | deal_activity | True |
| `hs_last_shared_message_create_date` | Last Shared Message Create Date | datetime | calculation_rollup | deal_activity | True |
| `hs_lastmodifieddate` | Last Modified Date | datetime | date | deal_activity | True |
| `hs_latest_approval_status` | Latest Approval Status | string | text | deal_activity | True |
| `hs_latest_approval_status_approval_id` | Latest Approval Status Approval ID | number | number | deal_activity | True |
| `hs_net_pipeline_impact` | Net Pipeline Impact | number | number | deal_activity | True |
| `hs_num_associated_active_deal_registrations` | Number of Active Deal Registrations | number | number | deal_activity | True |
| `hs_num_associated_deal_registrations` | Number of Deal Registrations | number | number | deal_activity | True |
| `hs_num_associated_deal_splits` | Number of Deal Splits | number | number | deal_activity | True |
| `hs_primary_quote_data_updated_at` | Primary quote data updated at | datetime | date | deal_activity | True |
| `hs_synced_deal_owner_name_and_email` | HubSpot Sales Lead | string | text | deal_activity | True |
| `hubspot_owner_assigneddate` | Owner assigned date | datetime | date | deal_activity | True |
| `notes_last_contacted` | Last Contacted | datetime | date | deal_activity | True |
| `notes_last_updated` | Last Activity Date | datetime | date | deal_activity | True |
| `notes_next_activity_date` | Next Activity Date | datetime | date | deal_activity | True |
| `num_contacted_notes` | Number of times contacted | number | number | deal_activity | True |
| `num_notes` | Number of Sales Activities | number | number | deal_activity | True |
| `pipeline` | Pipeline | enumeration | select | deal_activity | True |
| `amount` | Amount | number | number | deal_revenue | True |
| `amount_in_home_currency` | Amount in company currency | number | calculation_equation | deal_revenue | True |
| `deal_currency_code` | Currency | enumeration | select | deal_revenue | True |
| `hs_acv` | Annual contract value | number | number | deal_revenue | True |
| `hs_arr` | Annual recurring revenue | number | number | deal_revenue | True |
| `hs_exchange_rate` | Exchange rate | number | number | deal_revenue | True |
| `hs_mrr` | Monthly recurring revenue | number | number | deal_revenue | True |
| `hs_tcv` | Total contract value | number | number | deal_revenue | True |
| `closedate` | Close Date | datetime | date | dealinformation | True |
| `createdate` | Create Date | datetime | date | dealinformation | True |
| `days_to_close` | Days to close | number | calculation_equation | dealinformation | True |
| `dealname` | Deal Name | string | text | dealinformation | True |
| `dealtype` | Deal Type | enumeration | radio | dealinformation | True |
| `description` | Deal Description | string | textarea | dealinformation | True |
| `hs_actual_duration` | Actual duration | number | calculation_equation | dealinformation | True |
| `hs_all_accessible_team_ids` | All teams | enumeration | select | dealinformation | True |
| `hs_all_assigned_business_unit_ids` | Brands | enumeration | checkbox | dealinformation | True |
| `hs_all_collaborator_owner_ids` | Deal Collaborator | enumeration | checkbox | dealinformation | True |
| `hs_all_deal_split_owner_ids` | Deal Split Users | enumeration | checkbox | dealinformation | True |
| `hs_all_owner_ids` | All owner IDs | enumeration | select | dealinformation | True |
| `hs_all_team_ids` | All team IDs | enumeration | select | dealinformation | True |
| `hs_attributed_team_ids` | Attributed reporting team | enumeration | checkbox | dealinformation | True |
| `hs_campaign` | HubSpot Campaign | string | text | dealinformation | True |
| `hs_closed_amount` | Closed Deal Amount | number | calculation_equation | dealinformation | True |
| `hs_closed_amount_in_home_currency` | Closed deal amount in home currency | number | calculation_equation | dealinformation | True |
| `hs_closed_won_count` | Closed won count | number | calculation_equation | dealinformation | True |
| `hs_closed_won_date` | Closed Won Date (Internal) | datetime | date | dealinformation | True |
| `hs_created_by_user_id` | Created by user ID | number | number | dealinformation | True |
| `hs_createdate` | HubSpot Create Date | datetime | date | dealinformation | True |
| `hs_days_to_close_raw` | Days to close (without rounding) | number | calculation_equation | dealinformation | True |
| `hs_deal_amount_calculation_preference` | Deal amount calculation preference | enumeration | radio | dealinformation | True |
| `hs_deal_score` | Deal Score | number | number | dealinformation | True |
| `hs_deal_stage_probability` | Deal probability | number | number | dealinformation | True |
| `hs_deal_stage_probability_shadow` | Deal stage probability shadow | number | calculation_equation | dealinformation | True |
| `hs_forecast_amount` | Forecast amount | number | number | dealinformation | True |
| `hs_forecast_probability` | Forecast probability | number | number | dealinformation | True |
| `hs_form_id` | Form ID | string | calculation_rollup | dealinformation | True |
| `hs_has_empty_conditional_stage_properties` | Has Empty Conditional Stage Properties | bool | booleancheckbox | dealinformation | True |
| `hs_is_closed` | Is Deal Closed? | bool | calculation_equation | dealinformation | True |
| `hs_is_closed_count` | Is Closed (numeric) | number | calculation_equation | dealinformation | True |
| `hs_is_deal_split` | Deal Split Added | bool | calculation_equation | dealinformation | True |
| `hs_is_in_first_deal_stage` | Is In First Deal Stage | bool | booleancheckbox | dealinformation | True |
| `hs_is_open_count` | Is Open (numeric) | number | calculation_equation | dealinformation | True |
| `hs_latest_meeting_activity` | Latest meeting activity | datetime | date | dealinformation | True |
| `hs_likelihood_to_close` | Likelihood to close by the close date | number | number | dealinformation | True |
| `hs_line_item_global_term_hs_discount_percentage` | Global Term Line Item Discount Percentage | string | text | dealinformation | True |
| `hs_line_item_global_term_hs_discount_percentage_enabled` | Global Term Line Item Discount Percentage Enabled | bool | booleancheckbox | dealinformation | True |
| `hs_line_item_global_term_hs_recurring_billing_period` | Global Term Line Item Recurring Billing Period | string | text | dealinformation | True |
| `hs_line_item_global_term_hs_recurring_billing_period_enabled` | Global Term Line Item Recurring Billing Period Enabled | bool | booleancheckbox | dealinformation | True |
| `hs_line_item_global_term_hs_recurring_billing_start_date` | Global Term Line Item Recurring Billing Start Date | string | text | dealinformation | True |
| `hs_line_item_global_term_hs_recurring_billing_start_date_enabled` | Global Term Line Item Recurring Billing Start Date Enabled | bool | booleancheckbox | dealinformation | True |
| `hs_line_item_global_term_recurringbillingfrequency` | Global Term Line Item Recurring Billing Frequency | string | text | dealinformation | True |
| `hs_line_item_global_term_recurringbillingfrequency_enabled` | Global Term Line Item Recurring Billing Frequency Enabled | bool | booleancheckbox | dealinformation | True |
| `hs_manual_campaign_ids` | Manual campaign ids | number | calculation_rollup | dealinformation | True |
| `hs_manual_forecast_category` | Forecast category | enumeration | select | dealinformation | True |
| `hs_merged_object_ids` | Merged Deal IDs | enumeration | checkbox | dealinformation | True |
| `hs_next_meeting_id` | Next Meeting | number | number | dealinformation | True |
| `hs_next_meeting_name` | Next Meeting Name | string | text | dealinformation | True |
| `hs_next_meeting_start_time` | Next Meeting Start Time | datetime | date | dealinformation | True |
| `hs_next_step` | Next step | string | textarea | dealinformation | True |
| `hs_next_step_updated_at` | Next Step Updated At | datetime | calculation_equation | dealinformation | True |
| `hs_notes_last_activity` | Last Activity | object_coordinates | text | dealinformation | True |
| `hs_notes_next_activity` | Next Activity | object_coordinates | text | dealinformation | True |
| `hs_notes_next_activity_type` | Next Activity Type | enumeration | select | dealinformation | True |
| `hs_num_of_associated_line_items` | Number of Associated Line Items | number | number | dealinformation | True |
| `hs_num_target_accounts` | Number of target accounts | number | number | dealinformation | True |
| `hs_object_id` | Record ID | number | number | dealinformation | True |
| `hs_object_source` | Record creation source | string | text | dealinformation | True |
| `hs_object_source_detail_1` | Record source detail 1 | string | text | dealinformation | True |
| `hs_object_source_detail_2` | Record source detail 2 | string | text | dealinformation | True |
| `hs_object_source_detail_3` | Record source detail 3 | string | text | dealinformation | True |
| `hs_object_source_id` | Record creation source ID | string | text | dealinformation | True |
| `hs_object_source_label` | Record source | enumeration | select | dealinformation | True |
| `hs_object_source_user_id` | Record creation source user ID | number | number | dealinformation | True |
| `hs_owning_teams` | Owning Teams | enumeration | checkbox | dealinformation | True |
| `hs_partner_tech_win` | Partner Tech Win | enumeration | select | dealinformation | True |
| `hs_pinned_engagement_id` | Pinned Engagement ID | number | number | dealinformation | True |
| `hs_predicted_amount` | The predicted deal amount | number | calculation_equation | dealinformation | True |
| `hs_predicted_amount_in_home_currency` | The predicted deal amount in your company's currency | number | calculation_equation | dealinformation | True |
| `hs_price_book_reassignment_status` | Price book reassignment status | enumeration | select | dealinformation | True |
| `hs_primary_associated_company` | Primary Associated Company | number | calculation_rollup | dealinformation | True |
| `hs_priority` | Priority | enumeration | select | dealinformation | True |
| `hs_projected_amount` | Weighted amount | number | calculation_equation | dealinformation | True |
| `hs_projected_amount_in_home_currency` | Weighted amount in company currency | number | calculation_equation | dealinformation | True |
| `hs_read_only` | Read only object | bool | booleancheckbox | dealinformation | True |
| `hs_sales_email_last_replied` | Recent Sales Email Replied Date | datetime | date | dealinformation | True |
| `hs_shared_team_ids` | Shared teams | enumeration | checkbox | dealinformation | True |
| `hs_shared_user_ids` | Shared users | enumeration | checkbox | dealinformation | True |
| `hs_source_object_id` | Source Object ID | number | number | dealinformation | True |
| `hs_submission_idempotent_id` | Submission Idempotent ID | string | text | dealinformation | True |
| `hs_tag_ids` | Deal Tags | enumeration | checkbox | dealinformation | True |
| `hs_unique_creation_key` | Unique creation key | string | text | dealinformation | True |
| `hs_updated_by_user_id` | Updated by user ID | number | number | dealinformation | True |
| `hs_user_ids_of_all_notification_followers` | User IDs of all notification followers | enumeration | checkbox | dealinformation | True |
| `hs_user_ids_of_all_notification_recipients` | Deal record followers | enumeration | checkbox | dealinformation | True |
| `hs_user_ids_of_all_notification_unfollowers` | User IDs of all notification unfollowers | enumeration | checkbox | dealinformation | True |
| `hs_user_ids_of_all_owners` | User IDs of all owners | enumeration | checkbox | dealinformation | True |
| `hs_was_imported` | Performed in an import | bool | booleancheckbox | dealinformation | True |
| `hubspot_owner_id` | Deal owner | enumeration | select | dealinformation | True |
| `hubspot_team_id` | HubSpot Team | enumeration | select | dealinformation | True |
| `num_associated_contacts` | Number of Associated Contacts | number | calculation_rollup | dealinformation | True |
| `hs_average_deal_owner_duration_in_current_stage` | Average Deal Owner Duration In Current Stage | number | number | dealscripted | True |
| `hs_closed_deal_close_date` | Closed Deal Close Date | number | calculation_equation | dealscripted | True |
| `hs_closed_deal_create_date` | Closed Deal Create Date | number | calculation_equation | dealscripted | True |
| `hs_is_stalled` | Is Stalled | bool | calculation_equation | dealscripted | True |
| `hs_is_stalled_after_timestamp` | Is Stalled After Timestamp | datetime | date | dealscripted | True |
| `hs_open_deal_create_date` | Open deal create date | number | calculation_equation | dealscripted | True |
| `hs_v2_cumulative_time_in_appointmentscheduled` | Cumulative time in "Appointment Scheduled (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_cumulative_time_in_closedlost` | Cumulative time in "Closed Lost (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_cumulative_time_in_closedwon` | Cumulative time in "Closed Won (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_cumulative_time_in_contractsent` | Cumulative time in "Contract Sent (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_cumulative_time_in_decisionmakerboughtin` | Cumulative time in "Decision Maker Bought-In (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_cumulative_time_in_presentationscheduled` | Cumulative time in "Presentation Scheduled (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_cumulative_time_in_qualifiedtobuy` | Cumulative time in "Qualified To Buy (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_date_entered_appointmentscheduled` | Date entered "Appointment Scheduled (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_entered_closedlost` | Date entered "Closed Lost (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_entered_closedwon` | Date entered "Closed Won (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_entered_contractsent` | Date entered "Contract Sent (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_entered_current_stage` | Date entered current stage | datetime | calculation_equation | dealstages | True |
| `hs_v2_date_entered_decisionmakerboughtin` | Date entered "Decision Maker Bought-In (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_entered_presentationscheduled` | Date entered "Presentation Scheduled (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_entered_qualifiedtobuy` | Date entered "Qualified To Buy (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_exited_appointmentscheduled` | Date exited "Appointment Scheduled (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_exited_closedlost` | Date exited "Closed Lost (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_exited_closedwon` | Date exited "Closed Won (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_exited_contractsent` | Date exited "Contract Sent (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_exited_decisionmakerboughtin` | Date exited "Decision Maker Bought-In (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_exited_presentationscheduled` | Date exited "Presentation Scheduled (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_date_exited_qualifiedtobuy` | Date exited "Qualified To Buy (Sales Pipeline)" | datetime | date | dealstages | True |
| `hs_v2_latest_time_in_appointmentscheduled` | Latest time in "Appointment Scheduled (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_latest_time_in_closedlost` | Latest time in "Closed Lost (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_latest_time_in_closedwon` | Latest time in "Closed Won (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_latest_time_in_contractsent` | Latest time in "Contract Sent (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_latest_time_in_decisionmakerboughtin` | Latest time in "Decision Maker Bought-In (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_latest_time_in_presentationscheduled` | Latest time in "Presentation Scheduled (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_latest_time_in_qualifiedtobuy` | Latest time in "Qualified To Buy (Sales Pipeline)" | number | number | dealstages | True |
| `hs_v2_time_in_current_stage` | Time in current stage | datetime | calculation_equation | dealstages | True |
| `hs_open_amount_in_home_currency` | Open amount in home currency | number | calculation_equation | hubspotmetrics | True |
| `hs_weighted_pipeline_in_company_currency` | Weighted open pipeline in company currency | number | calculation_equation | hubspotmetrics | True |
| `hs_cross_account_note` | Cross-account note | string | textarea | multiaccountmanagement | True |
| `hs_cross_sell_opportunity` | Cross-sell Opportunity | bool | booleancheckbox | multiaccountmanagement | True |
| `hs_average_call_duration` | Average call duration | number | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_latest_marketing_email_click_date` | Latest marketing email click date | datetime | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_latest_marketing_email_open_date` | Latest marketing email open date | datetime | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_latest_marketing_email_reply_date` | Latest marketing email reply date | datetime | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_latest_sales_email_click_date` | Latest sales email click date | datetime | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_latest_sales_email_open_date` | Latest sales email open date | datetime | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_latest_sales_email_reply_date` | Latest sales email reply date | datetime | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_number_of_call_engagements` | Number of call engagements | number | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_number_of_inbound_calls` | Number of inbound calls | number | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_number_of_outbound_calls` | Number of outbound calls | number | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_number_of_overdue_tasks` | Number of overdue tasks | number | calculation_rollup | predictive_deal_score_feature_properties | True |
| `hs_number_of_scheduled_meetings` | Number of scheduled meetings | number | calculation_rollup | predictive_deal_score_feature_properties | True |

## Pipelines and stages

### Sales Pipeline (`default`)

| stage id | label | probability | closed |
|---|---|---|---|
| `appointmentscheduled` | Appointment Scheduled | 0.2 | false |
| `qualifiedtobuy` | Qualified To Buy | 0.4 | false |
| `presentationscheduled` | Presentation Scheduled | 0.6 | false |
| `decisionmakerboughtin` | Decision Maker Bought-In | 0.8 | false |
| `contractsent` | Contract Sent | 0.9 | false |
| `closedwon` | Closed Won | 1.0 | true |
| `closedlost` | Closed Lost | 0.0 | true |

