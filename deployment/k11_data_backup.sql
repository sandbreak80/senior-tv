-- settings: 26 rows
INSERT OR REPLACE INTO settings (key,value) VALUES ('greeting_names','Colleen & Don');
INSERT OR REPLACE INTO settings (key,value) VALUES ('weather_lat','33.7083');
INSERT OR REPLACE INTO settings (key,value) VALUES ('weather_lon','-117.1972');
INSERT OR REPLACE INTO settings (key,value) VALUES ('weather_unit','fahrenheit');
INSERT OR REPLACE INTO settings (key,value) VALUES ('news_feeds','https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml');
INSERT OR REPLACE INTO settings (key,value) VALUES ('jellyfin_url','http://192.168.50.20:8096');
INSERT OR REPLACE INTO settings (key,value) VALUES ('jellyfin_api_key','001173c5b6c54cc5bdb79371279dc3a4');
INSERT OR REPLACE INTO settings (key,value) VALUES ('jellyfin_user_id','fba7eb5e0c044d4cb9a8ad1c82e2cb8c');
INSERT OR REPLACE INTO settings (key,value) VALUES ('frigate_url','http://192.168.50.114:5000');
INSERT OR REPLACE INTO settings (key,value) VALUES ('frigate_user','');
INSERT OR REPLACE INTO settings (key,value) VALUES ('frigate_pass','');
INSERT OR REPLACE INTO settings (key,value) VALUES ('frigate_cameras','front_door');
INSERT OR REPLACE INTO settings (key,value) VALUES ('ha_url','http://192.168.50.76:8123');
INSERT OR REPLACE INTO settings (key,value) VALUES ('ha_token','eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJkYjZmNDI1ZTYxYmI0MjMzOTVhZGMyZThkMDgxZDUwMCIsImlhdCI6MTc3NDE0NTIxOSwiZXhwIjoyMDg5NTA1MjE5fQ.dmOA7aSYaABsiEOhhcqoKSyhYCSLHc8MLyiUgmAVoBo');
INSERT OR REPLACE INTO settings (key,value) VALUES ('photo_interval','10');
INSERT OR REPLACE INTO settings (key,value) VALUES ('photo_nas_path','');
INSERT OR REPLACE INTO settings (key,value) VALUES ('immich_url','http://192.168.50.165:2283');
INSERT OR REPLACE INTO settings (key,value) VALUES ('immich_api_key','PtVLRDymqf7t3Ia7EY7TC9qDNuFFjXNc5qw4x0w');
INSERT OR REPLACE INTO settings (key,value) VALUES ('admin_password','family2026');
INSERT OR REPLACE INTO settings (key,value) VALUES ('ha_tv_entity','media_player.living_room_tv_qn65q60aafxza');
INSERT OR REPLACE INTO settings (key,value) VALUES ('classical_music_enabled','1');
INSERT OR REPLACE INTO settings (key,value) VALUES ('classical_music_hour','10');
INSERT OR REPLACE INTO settings (key,value) VALUES ('tts_enabled','1');
INSERT OR REPLACE INTO settings (key,value) VALUES ('voice_boost','mild');
INSERT OR REPLACE INTO settings (key,value) VALUES ('audio_target','-14');
INSERT OR REPLACE INTO settings (key,value) VALUES ('audio_processing','0');

-- pills: 4 rows
INSERT OR REPLACE INTO pills (id,name,dosage,instructions,schedule_times,schedule_days,reminder_type,reminder_media,reminder_message,enabled,created_at) VALUES (1,'Morning Pills','','Take with water','["11:00"]','["mon", "tue", "wed", "thu", "fri", "sat", "sun"]','text',NULL,'Time to take your morning pills!',1,'2026-03-24 18:16:13');
INSERT OR REPLACE INTO pills (id,name,dosage,instructions,schedule_times,schedule_days,reminder_type,reminder_media,reminder_message,enabled,created_at) VALUES (2,'Evening Pills','','Take with water','["20:30"]','["mon", "tue", "wed", "thu", "fri", "sat", "sun"]','text',NULL,'Time to take your evening pills!',1,'2026-03-24 18:16:13');
INSERT OR REPLACE INTO pills (id,name,dosage,instructions,schedule_times,schedule_days,reminder_type,reminder_media,reminder_message,enabled,created_at) VALUES (3,'Shower Time','','','["08:00", "12:00", "16:00", "20:00"]','["tue", "thu"]','text',NULL,'Time for a shower! The TV will be back in 15 minutes.',0,'2026-03-24 18:16:13');
INSERT OR REPLACE INTO pills (id,name,dosage,instructions,schedule_times,schedule_days,reminder_type,reminder_media,reminder_message,enabled,created_at) VALUES (5,'Stretch Break','','Stand up and stretch for 15 minutes','["09:00", "13:00", "17:00", "21:00"]','["mon", "tue", "wed", "thu", "fri", "sat", "sun"]','text',NULL,'Time to stand up, stretch your arms and legs, and move around!',0,'2026-03-26 12:50:30');

-- birthdays: 2 rows
INSERT OR REPLACE INTO birthdays (id,name,birth_date,birth_year,relationship,created_at) VALUES (1,'Don','03-03',1931,'','2026-03-24 18:16:13');
INSERT OR REPLACE INTO birthdays (id,name,birth_date,birth_year,relationship,created_at) VALUES (2,'Colleen','03-16',1931,'','2026-03-24 18:16:13');

-- favorite_shows: 8 rows
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (1,'Jeopardy','jeopardy',1,'2026-03-24 18:16:14');
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (2,'Two and a Half Men','two and a half',0,'2026-03-24 18:16:14');
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (3,'Law & Order','law & order',0,'2026-03-24 18:16:14');
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (4,'Criminal Minds','criminal minds',0,'2026-03-24 18:16:14');
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (5,'CSI','csi',0,'2026-03-24 18:16:14');
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (6,'Dateline','dateline',0,'2026-03-24 18:16:14');
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (8,'Bonanza','bonanza',0,'2026-03-24 18:16:14');
INSERT OR REPLACE INTO favorite_shows (id,name,search_term,enabled,created_at) VALUES (9,'Gunsmoke','gunsmoke',0,'2026-03-24 18:16:14');

-- youtube_channels: 58 rows
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (37,'The Carol Burnett Show','UCry6nxAo2tfVyO6lEboiU3w','Official Carol Burnett Show channel with classic sketches',NULL,'Classic TV',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (38,'I Love Lucy','UCOiYFgUGMIB1lE-1xhEwtvA','Classic I Love Lucy episodes and clips',NULL,'Classic TV',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (39,'The Beverly Hillbillies','UC21t6T1ke_VrKXTTa5HV4qg','Beverly Hillbillies full episodes',NULL,'Classic TV',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (40,'The Andy Griffith Show','UCoxXgw3jrdMcUHewguYRjKA','Andy Griffith Show clips and episodes',NULL,'Classic TV',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (41,'The Ed Sullivan Show','UCDUNe-NZaknJOGyulc4Ohvg','Official Ed Sullivan Show - classic performances',NULL,'Classic TV',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (42,'Jeopardy!','UCnxxhf9PSA3VJ4Q80pWJoow','Official Jeopardy! channel',NULL,'Game Shows',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (43,'Wheel of Fortune','UCeo7caZ6hsO7CQuDZ8AywEQ','Official Wheel of Fortune channel',NULL,'Game Shows',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (44,'The Price Is Right','UCbiB7lO-l6SP--bvA4fOLEw','Official Price Is Right channel',NULL,'Game Shows',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (45,'Family Feud','UCt8jfvd9skBAOT6XJwc_mJg','Official Family Feud channel',NULL,'Game Shows',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (46,'Game Show Network','UCTparG3LaC_RDcXgkMorytA','GSN classic game show clips',NULL,'Game Shows',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (47,'BUZZR','UCNkETBwkARrGDx-G7P-jLJg','Classic game show network',NULL,'Game Shows',6,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (48,'Bonanza','UC9sgp2gveE8SXbsvXCx-01Q','Bonanza full episodes',NULL,'Westerns',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (49,'Gunsmoke','UC_gxbZs2wNZ0zE1pRw2PnjQ','Gunsmoke western TV episodes',NULL,'Westerns',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (50,'Grjngo - Western Movies','UCyJYCQ6WaEMhdZAuPo799bA','Free full-length western movies',NULL,'Westerns',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (51,'Grjngo - Western Series','UCzmxp3B3pA1pE2RHGAaRtVA','Free western TV series episodes',NULL,'Westerns',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (52,'Classic Western Movie','UCjce8ThT14hk7iccpzaVMvQ','Classic western movie compilations',NULL,'Westerns',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (53,'Johnny Carson','UC7McHNOsrUL2fRxTB_xvgRQ','Classic Tonight Show with Johnny Carson',NULL,'Music & Variety',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (54,'Country''s Family Reunion','UCVh1ZR1OrEnni7HSbaDGnIg','Country music legends performing together',NULL,'Music & Variety',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (55,'Oldies Music Radio','UCaZDizLXZkR0V2DkZGEWeYw','50s, 60s, 70s oldies music compilations',NULL,'Music & Variety',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (56,'Oldies Sweet Memories','UC4JQKqZfuH1eaoLLLD9rBdw','Classic oldies music compilations',NULL,'Music & Variety',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (57,'Lawrence Welk LPs','UCepuqk1t-8J1nByerAKfP7g','Lawrence Welk Show music and performances',NULL,'Music & Variety',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (58,'Bob Ross','UCxcnsr1R5Ge_fbTu5ajt8DQ','The Joy of Painting with Bob Ross',NULL,'Wind Down',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (59,'BBC Earth','UCwmZiChSryoWQCZMIQezgTg','Nature documentaries from BBC',NULL,'Wind Down',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (60,'Nature Relaxation Films','UC4lp9Emg1ci8eo2eDkB-Tag','4K nature scenery and relaxing videos',NULL,'Wind Down',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (61,'4K Relaxation Channel','UCg72Hd6UZAgPBAUZplnmPMQ','4K ambient nature, aquarium, fireplace videos',NULL,'Wind Down',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (62,'BBC Earth Relax','UC4dMNPt9AGb_o2GwVBf_qNA','Calming nature footage for relaxation',NULL,'Wind Down',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (63,'America''s Funniest Home Videos','UC_zEzzq54Rm0iy7lmmZbCIg','Official AFV funny video clips',NULL,'Comedy',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (64,'Comedy Central','UCrRttZIypNTA1Mrfwo745Sg','Stand-up comedy and sketches',NULL,'Comedy',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (65,'Netflix Is A Joke','UCVTyTA7-g9nopHeHbeuvpRA','Netflix stand-up comedy specials',NULL,'Comedy',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (66,'Whose Line Is It Anyway','UCYyyvqxS9jV6TebIK-g1nwQ','Improv comedy show clips',NULL,'Comedy',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (67,'AFV Classics','UC-5Kr2sFSJf8jGjyRJ-4H8Q','Classic Americas Funniest Home Videos',NULL,'Comedy',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (68,'ABC News','UCBi2mrWuNuyYy4gbM6fU18Q','ABC News live and clips',NULL,'Morning Shows',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (69,'CBS News','UC8p1vwvWtl6T73JiExfWs1g','CBS News live and clips',NULL,'Morning Shows',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (70,'NBC News','UCeY0bbntWzzVIaj2z3QigXg','NBC News live and clips',NULL,'Morning Shows',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (71,'CBS Sunday Morning','UCVT1tPkR-fUVlO652EcO3ow','CBS Sunday Morning features and interviews',NULL,'Morning Shows',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (72,'60 Minutes','UCsN32BtMd0IoByjJRNF12cw','60 Minutes investigative journalism',NULL,'Morning Shows',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (73,'Dateline NBC','UCu3sKtOW9TGaErPsAYVPplA','Dateline NBC true crime stories',NULL,'Crime & Drama',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (74,'48 Hours','UC7htuVs06oduI3xSfTdcxPA','CBS 48 Hours true crime investigations',NULL,'Crime & Drama',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (75,'COURT TV','UCo5E9pEhK_9kWG7-5HHcyRg','Live court proceedings and legal analysis',NULL,'Crime & Drama',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (76,'Law & Crime Network','UCz8K1occVvDTYDfFo7N5EZw','True crime trials and legal coverage',NULL,'Crime & Drama',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (77,'Criminal Minds','UClzCn8DxRSCuMFv_WfzkcrQ','Criminal Minds TV show clips',NULL,'Crime & Drama',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (78,'ABC7 Los Angeles','UCVxBA3Cbu3pm8w8gEIoMEog','KABC Los Angeles local news',NULL,'Local News',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (79,'CBS LA','UCkH1uDkyuO9sVjSqdqBygOg','KCAL/CBS Los Angeles local news',NULL,'Local News',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (80,'NBCLA','UCSWoppsVL0TLxFQ2qP_DLqQ','NBC Los Angeles local news',NULL,'Local News',3,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (81,'FOX 11 Los Angeles','UCHfF8wFnipMeDpJf8OmMxDg','FOX 11 LA local news',NULL,'Local News',4,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (82,'KTLA 5','UCinjnmQEwCddOudyCC1v7qA','KTLA Los Angeles local news',NULL,'Local News',5,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (83,'Nat Geo Wild','UCDPk9MG2RexnOMGTD-YnSnA','National Geographic Wild nature documentaries',NULL,'Nature',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (84,'Rick Steves Europe','UCchgIh8Tc4sTmBfnMQ5pDdg','Travel through Europe with Rick Steves',NULL,'Nature',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (85,'America''s Test Kitchen','UCxAS_aK7sS2x_bqnlJHDSHw','Cooking recipes and kitchen tips',NULL,'Cooking',1,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (86,'Tasty','UCJFp8uSYCjXOMnkUyb3CQ3Q','Quick cooking videos and recipes',NULL,'Cooking',2,'2026-03-26 12:38:30');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (87,'Classical Music','UClScm1QV2xecmZrAuADnP9g','Classical piano, orchestra, relaxing','','Wind Down',10,'2026-03-26 12:52:18');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (88,'Scenic Relaxation','UC95bEkaIgwhxSjSsdMFXYGg','4K scenic films worldwide with calming music','','Wind Down',20,'2026-03-26 14:11:54');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (89,'Relaxation Film','UCPotnGNahFjLWjfsq4KYvuQ','4K/8K nature journeys with meditation music','','Wind Down',21,'2026-03-26 14:11:54');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (90,'4K Relaxation Film','UCbmwzr3DR6WRiSvHE9d56og','4K wildlife and nature with calm music','','Wind Down',22,'2026-03-26 14:11:54');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (91,'Soothing Relaxation','UCjzHeG1KWoonmf9d5KBvSiw','Piano music with nature scenery','','Wind Down',23,'2026-03-26 14:11:54');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (92,'Prowalk Tours','UCNzul4dnciIlDg8BAcn5-cQ','4K city walking tours worldwide','','Wind Down',24,'2026-03-26 14:11:54');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (93,'Watched Walker','UC_mzz_JnzArhhpGUy8KdGwg','4K HDR walks through London and world cities','','Wind Down',25,'2026-03-26 14:11:54');
INSERT OR REPLACE INTO youtube_channels (id,name,channel_id,description,thumbnail_url,category,sort_order,created_at) VALUES (94,'Rambalac','UCAcsAE1tpLuP3y7UhxUoWpQ','4K walks through Japan, no narration','','Wind Down',26,'2026-03-26 14:11:54');

-- calendar_events: 21 rows
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (1,'🎉 New Year''s Day','New Year''s Day','2026-01-01',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (2,'🎉 Martin Luther King, Jr. Day','Martin Luther King, Jr. Day','2026-01-19',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (3,'🎉 Washington''s Birthday','Presidents Day','2026-02-16',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (4,'🎉 Memorial Day','Memorial Day','2026-05-25',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (5,'🎉 Juneteenth National Independence Day','Juneteenth National Independence Day','2026-06-19',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (6,'🎉 Independence Day','Independence Day','2026-07-03',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (7,'🎉 Labor Day','Labour Day','2026-09-07',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (8,'🎉 Veterans Day','Veterans Day','2026-11-11',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (9,'🎉 Thanksgiving Day','Thanksgiving Day','2026-11-26',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (10,'🎉 Christmas Day','Christmas Day','2026-12-25',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (11,'🎉 New Year''s Day','New Year''s Day','2027-01-01',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (12,'🎉 Martin Luther King, Jr. Day','Martin Luther King, Jr. Day','2027-01-18',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (13,'🎉 Washington''s Birthday','Presidents Day','2027-02-15',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (14,'🎉 Memorial Day','Memorial Day','2027-05-31',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (15,'🎉 Juneteenth National Independence Day','Juneteenth National Independence Day','2027-06-18',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (16,'🎉 Independence Day','Independence Day','2027-07-05',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (17,'🎉 Labor Day','Labour Day','2027-09-06',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (18,'🎉 Veterans Day','Veterans Day','2027-11-11',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (19,'🎉 Thanksgiving Day','Thanksgiving Day','2027-11-25',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (20,'🎉 Christmas Day','Christmas Day','2027-12-24',NULL,'yearly','2026-03-24 18:16:14');
INSERT OR REPLACE INTO calendar_events (id,title,description,event_date,event_time,recurring,created_at) VALUES (21,'Doctor Appointment - phone call','doctor phone call
both Don and Colleen','2026-03-30','13:00',NULL,'2026-03-26 19:11:44');

