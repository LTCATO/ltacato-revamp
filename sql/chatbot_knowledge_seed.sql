-- Run in Supabase SQL editor. Bulk-inserts FAQ entries into chatbot_knowledge
-- so you don't have to add them one by one in the dashboard's "Add FAQ entry"
-- form. approval_status is set to 'approved' so every row is immediately
-- active in LARA's knowledge base (same effect as super_admin/ltcato_staff
-- adding an entry through the UI, which auto-approves).
--
-- Edit/add/remove rows below to match your real FAQ content, then run.
-- created_by/approved_by are left NULL (nullable columns) since these are
-- being added directly, not through a dashboard user's session.
--
-- Note: chatbot_knowledge has no UNIQUE constraint on question/answer, so
-- running this script twice will insert duplicates — remove rows you've
-- already added before re-running, rather than relying on this to dedupe.

INSERT INTO chatbot_knowledge (question, answer, category, approval_status)
VALUES
  (
    'What is the best time to visit Laguna?',
    'The dry season (December to May) is generally best — cooler and less rainy from December to February, warmer and best for swimming or resorts from March to May. The wet season (June to November) brings frequent rain that can affect waterfalls and outdoor events.',
    'General',
    'approved'
  ),
  (
    'Is there an entrance fee for tourist spots in Laguna?',
    'Entrance fees vary by spot — most resorts and waterfalls charge a small fee (typically PHP 50-200), while public heritage sites like churches are usually free. Check each spot''s listing on the site for its specific entrance fee.',
    'Fees',
    'approved'
  ),
  (
    'What should I bring when visiting waterfalls or nature spots?',
    'Bring a change of clothes, water shoes or sandals with good grip, a dry bag for electronics, sunscreen, insect repellent, and drinking water. Some spots also require a life vest, which is often available for rent on-site.',
    'General',
    'approved'
  ),
  (
    'Are pets allowed at tourist spots in Laguna?',
    'Pet policies vary by establishment. Many outdoor nature spots and resorts do allow leashed pets, but some heritage sites and indoor attractions do not. Contact the specific spot ahead of your visit to confirm.',
    'General',
    'approved'
  ),
  (
    'How do I claim or register my establishment on this platform?',
    'Establishment owners can register through the dashboard sign-up flow, then either register a new tourist spot or claim an existing unclaimed listing in their LGU. Your listing goes through LGU and LTCATO review before appearing publicly.',
    'For Owners',
    'approved'
  ),
  (
    'How do I submit a tourist arrival report?',
    'LGU admins and establishment owners can submit daily, weekly, or monthly arrival reports through the dashboard''s Arrival Reports section, breaking down visitors by origin (same city, other city, other province, foreign) and gender.',
    'For LGU Admins',
    'approved'
  ),
  (
    'What payment methods are accepted at tourist spots?',
    'This varies by establishment — many smaller spots in Laguna are cash-only, while resorts and larger attractions increasingly accept GCash or cards. It''s best to bring cash as a backup when visiting rural or nature spots.',
    'Fees',
    'approved'
  ),
  (
    'Who created LARA?',
    'LARA (Laguna AI Tourism Assistant) was created and programmed by the LTCATO Development Team (Laguna Tourism, Culture, Arts and Trade Office), with special mention to Lawrence Celis.',
    'General',
    'approved'
  ),
  (
    'Is it safe to visit waterfalls during the rainy season?',
    'Exercise caution — heavy rain can cause flash floods and strong currents at waterfalls, and some trails may be closed for safety. Check local advisories before visiting, and consider indoor or urban attractions as alternatives during typhoons.',
    'Safety',
    'approved'
  ),
  (
    'What language do people speak in Laguna?',
    'Filipino (Tagalog) is the primary language, and English is widely understood and spoken, especially at tourist establishments. Some locals also speak regional languages, but you''ll get by comfortably with English or basic Tagalog.',
    'General',
    'approved'
  ),
  (
    'Is there mobile signal and wifi at tourist spots in Laguna?',
    'Signal is generally reliable in cities and town centers (Calamba, Santa Rosa, San Pablo), but can be weak or spotty at remote waterfalls, mountain trails, and rural nature spots. Don''t rely on constant connectivity once you''re off the main roads.',
    'General',
    'approved'
  ),
  (
    'How do I get around Laguna without a car?',
    'Public buses and UV Express vans run between Manila and major Laguna towns via SLEX. Within and between municipalities, jeepneys and tricycles are the main local transport — tricycles are best for the last stretch to specific tourist spots.',
    'Transportation',
    'approved'
  ),
  (
    'Are there ATMs near tourist spots in Laguna?',
    'ATMs are common in city centers like Calamba, Santa Rosa, San Pablo, and Los Baños, but scarce or nonexistent near rural waterfalls and nature spots. Withdraw cash before heading to remote destinations.',
    'Fees',
    'approved'
  ),
  (
    'What local food should I try in Laguna?',
    'Laguna is known for buko pie (especially from Los Baños), kesong puti (white cheese) from Sta. Cruz, espasol, and itlog na maalat (salted eggs). Many towns also have their own local delicacies worth trying.',
    'General',
    'approved'
  ),
  (
    'Can I bring my own food and drinks to tourist spots?',
    'This depends on the specific establishment — many resorts and nature spots allow outside food, while some charge a corkage fee or restrict it to encourage on-site purchases. Check the spot''s listing or ask on arrival.',
    'General',
    'approved'
  ),
  (
    'Is Laguna a good day trip from Manila?',
    'Yes — most Laguna tourist spots are 1.5 to 3 hours from Manila by road, making many of them doable as a day trip. For spots further south (like Cavinti or Luisiana), an overnight stay is more comfortable.',
    'General',
    'approved'
  ),
  (
    'What should I do in case of an emergency while visiting?',
    'For medical or safety emergencies, call 911 (nationwide emergency hotline). You can also reach out to the local barangay hall, police station, or the municipality''s tourism office nearest to where you are.',
    'Safety',
    'approved'
  ),
  (
    'Can I plan a multi-day itinerary using this platform?',
    'Yes — logged-in tourists can use the Itinerary Planner to build a multi-day trip, add tourist spots per day, and get estimated travel times between stops within Laguna.',
    'General',
    'approved'
  ),
  (
    'Do tourist spots in Laguna require a reservation or scheduled visit?',
    'It depends on the spot — some accept walk-ins freely, while others (especially smaller establishments) allow you to schedule a visit in advance through this platform to help manage crowd size.',
    'General',
    'approved'
  );
